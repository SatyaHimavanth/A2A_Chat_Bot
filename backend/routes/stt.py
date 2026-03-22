import asyncio
import json
import logging

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from core.auth_utils import verify_auth_token
from core.config import (
    STT_DEFAULT_PAUSE_MS,
    STT_ENDPOINT_SILENCE_MS,
    STT_MIN_VOICED_RATIO,
    STT_MODEL_ID,
    STT_NOISE_GATE_THRESHOLD,
    STT_PARTIAL_INTERVAL_MS,
    STT_PARTIAL_WINDOW_SECONDS,
    STT_SILENCE_RMS_THRESHOLD,
    STT_TARGET_SAMPLE_RATE,
)
from database import SessionLocal
from models import User
from services.stt_service import stt_service

router = APIRouter(tags=['stt'])
logger = logging.getLogger(__name__)


def _join_text(left: str, right: str) -> str:
    if not left.strip():
        return right.strip()
    if not right.strip():
        return left.strip()
    return f'{left.strip()} {right.strip()}'.strip()


def _pcm_rms(chunk: bytes) -> float:
    if not chunk:
        return 0.0
    samples = np.frombuffer(chunk, dtype=np.int16)
    if samples.size == 0:
        return 0.0
    normalized = samples.astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(np.square(normalized))))


def _voiced_ratio(pcm_bytes: bytes, threshold: float) -> float:
    if not pcm_bytes:
        return 0.0
    samples = np.frombuffer(pcm_bytes, dtype=np.int16)
    if samples.size == 0:
        return 0.0
    normalized = np.abs(samples.astype(np.float32) / 32768.0)
    return float(np.mean(normalized >= threshold))


async def _safe_send_json(websocket: WebSocket, payload: dict) -> bool:
    if websocket.application_state == WebSocketState.CONNECTED:
        try:
            await websocket.send_json(payload)
            return True
        except RuntimeError:
            return False
        except WebSocketDisconnect:
            return False
    return False


async def _safe_close(websocket: WebSocket, code: int = 1000, reason: str = '') -> None:
    if websocket.application_state != WebSocketState.DISCONNECTED:
        try:
            await websocket.close(code=code, reason=reason)
        except RuntimeError:
            pass
        except WebSocketDisconnect:
            pass


async def _authenticate_ws(websocket: WebSocket) -> User | None:
    token = (websocket.query_params.get('token') or '').strip()
    if not token:
        await _safe_close(websocket, code=4401, reason='Missing bearer token.')
        return None

    try:
        payload = verify_auth_token(token, expected_type='access')
    except Exception as exc:
        await _safe_close(websocket, code=4401, reason=str(getattr(exc, 'detail', exc)))
        return None

    user_id = payload.get('user_id')
    db = SessionLocal()
    try:
        user = db.get(User, user_id) if isinstance(user_id, int) else None
    finally:
        db.close()
    if not user:
        await _safe_close(websocket, code=4401, reason='User not found.')
        return None
    return user


@router.websocket('/api/stt/ws')
async def speech_to_text_ws(websocket: WebSocket):
    user = await _authenticate_ws(websocket)
    if user is None:
        return

    await websocket.accept()
    logger.info('STT websocket accepted for user_id=%s', user.id)
    await _safe_send_json(
        websocket,
        {
            'type': 'ready',
            'modelId': STT_MODEL_ID,
            'sampleRate': STT_TARGET_SAMPLE_RATE,
            'defaultPauseMs': STT_DEFAULT_PAUSE_MS,
        },
    )

    sample_rate = STT_TARGET_SAMPLE_RATE
    partial_interval_ms = STT_PARTIAL_INTERVAL_MS
    endpoint_silence_ms = STT_ENDPOINT_SILENCE_MS
    silence_rms_threshold = STT_SILENCE_RMS_THRESHOLD
    noise_gate_threshold = STT_NOISE_GATE_THRESHOLD
    min_voiced_ratio = STT_MIN_VOICED_RATIO

    committed_text = ''
    active_audio = bytearray()
    last_partial_audio_len = 0
    last_interim_text = ''
    silence_ms = 0
    stop_requested = False

    def _full_text_with_interim(interim: str = '') -> str:
        return _join_text(committed_text, interim)

    async def _emit_interim() -> None:
        nonlocal last_partial_audio_len, last_interim_text
        buffer_bytes = len(active_audio)
        if buffer_bytes == 0:
            return

        bytes_per_second = max(sample_rate * 2, 1)
        window_bytes = int(bytes_per_second * STT_PARTIAL_WINDOW_SECONDS)
        audio_bytes = (
            bytes(active_audio[-window_bytes:]) if window_bytes > 0 else bytes(active_audio)
        )

        await _safe_send_json(
            websocket,
            {
                'type': 'processing',
                'kind': 'interim',
                'bufferBytes': buffer_bytes,
                'windowBytes': len(audio_bytes),
            },
        )
        text = await stt_service.transcribe_pcm16(audio_bytes, sample_rate)
        last_partial_audio_len = buffer_bytes
        if not text.strip() or text.strip() == last_interim_text.strip():
            return

        last_interim_text = text.strip()
        await _safe_send_json(
            websocket,
            {
                'type': 'interim',
                'text': last_interim_text,
                'fullText': _full_text_with_interim(last_interim_text),
            },
        )

    async def _commit_active(reason: str) -> None:
        nonlocal committed_text, active_audio, last_partial_audio_len, last_interim_text, silence_ms
        if not active_audio:
            return
        voiced_ratio = _voiced_ratio(bytes(active_audio), noise_gate_threshold)
        if voiced_ratio < min_voiced_ratio:
            logger.info(
                'STT discarded active utterance as noise: reason=%s voiced_ratio=%.4f threshold=%.4f',
                reason,
                voiced_ratio,
                min_voiced_ratio,
            )
            active_audio = bytearray()
            last_partial_audio_len = 0
            last_interim_text = ''
            silence_ms = 0
            return

        await _safe_send_json(
            websocket,
            {
                'type': 'processing',
                'kind': 'commit',
                'reason': reason,
                'bufferBytes': len(active_audio),
            },
        )
        utterance_text = (await stt_service.transcribe_pcm16(bytes(active_audio), sample_rate)).strip()
        if utterance_text:
            committed_text = _join_text(committed_text, utterance_text)
            await _safe_send_json(
                websocket,
                {
                    'type': 'commit',
                    'text': utterance_text,
                    'fullText': committed_text,
                    'reason': reason,
                },
            )

        active_audio = bytearray()
        last_partial_audio_len = 0
        last_interim_text = ''
        silence_ms = 0

    try:
        while True:
            message = await websocket.receive()
            if message.get('type') == 'websocket.disconnect':
                break

            if message.get('text') is not None:
                payload = json.loads(message['text'])
                msg_type = payload.get('type')
                if msg_type == 'start':
                    sample_rate = int(payload.get('sampleRate') or STT_TARGET_SAMPLE_RATE)
                    partial_interval_ms = int(payload.get('partialIntervalMs') or STT_PARTIAL_INTERVAL_MS)
                    endpoint_silence_ms = int(payload.get('endpointSilenceMs') or STT_ENDPOINT_SILENCE_MS)
                    logger.info(
                        'STT start: sample_rate=%s partial_interval_ms=%s endpoint_silence_ms=%s',
                        sample_rate,
                        partial_interval_ms,
                        endpoint_silence_ms,
                    )
                    await stt_service.ensure_loaded()
                    continue

                if msg_type == 'stop':
                    stop_requested = True
                    await _commit_active('client_stop')
                    await _safe_send_json(
                        websocket,
                        {
                            'type': 'final',
                            'text': committed_text,
                            'fullText': committed_text,
                        },
                    )
                    break

            chunk = message.get('bytes')
            if not chunk:
                continue

            active_audio.extend(chunk)
            rms = _pcm_rms(chunk)
            chunk_ms = int((len(chunk) / max(sample_rate * 2, 1)) * 1000)
            if rms >= silence_rms_threshold:
                silence_ms = 0
            else:
                silence_ms += chunk_ms

            min_partial_bytes = int(sample_rate * 2 * (partial_interval_ms / 1000))
            if len(active_audio) - last_partial_audio_len >= min_partial_bytes:
                await _emit_interim()

            if silence_ms >= endpoint_silence_ms and len(active_audio) > 0:
                await _commit_active('silence_endpoint')
                await _safe_send_json(
                    websocket,
                    {
                        'type': 'state',
                        'status': 'listening',
                        'fullText': committed_text,
                    },
                )
    except WebSocketDisconnect:
        logger.info('STT websocket disconnected by client')
        return
    except asyncio.CancelledError:
        logger.info('STT websocket cancelled during shutdown')
        return
    except Exception as exc:
        logger.exception('STT websocket error: %s', exc)
        await _safe_send_json(websocket, {'type': 'error', 'message': str(exc)})
    finally:
        if stop_requested and websocket.application_state == WebSocketState.CONNECTED:
            await asyncio.sleep(0)
        await _safe_close(websocket)
        logger.info('STT websocket closed')
