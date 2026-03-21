import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from core.auth_utils import verify_auth_token
from core.config import (
    STT_DEFAULT_PAUSE_MS,
    STT_MODEL_ID,
    STT_PARTIAL_INTERVAL_MS,
    STT_PARTIAL_WINDOW_SECONDS,
    STT_TARGET_SAMPLE_RATE,
)
from database import SessionLocal
from models import User
from services.stt_service import stt_service

router = APIRouter(tags=['stt'])
logger = logging.getLogger(__name__)


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
    audio_buffer = bytearray()
    last_partial_audio_len = 0
    last_text = ''
    stop_requested = False

    async def emit_transcript(kind: str) -> None:
        nonlocal last_text, last_partial_audio_len
        buffer_bytes = len(audio_buffer)
        bytes_per_second = max(sample_rate * 2, 1)
        if kind == 'partial':
            window_bytes = int(bytes_per_second * STT_PARTIAL_WINDOW_SECONDS)
            audio_bytes = bytes(audio_buffer[-window_bytes:]) if window_bytes > 0 else bytes(audio_buffer)
        else:
            audio_bytes = bytes(audio_buffer)
        await _safe_send_json(
            websocket,
            {
                'type': 'processing',
                'kind': kind,
                'bufferBytes': buffer_bytes,
                'windowBytes': len(audio_bytes),
            },
        )
        logger.info(
            'STT emit requested: kind=%s buffer_bytes=%s window_bytes=%s sample_rate=%s',
            kind,
            buffer_bytes,
            len(audio_bytes),
            sample_rate,
        )
        text = await stt_service.transcribe_pcm16(audio_bytes, sample_rate)
        if kind == 'partial':
            last_partial_audio_len = buffer_bytes
        if kind == 'final' and not text.strip() and last_text.strip():
            text = last_text
        if text == last_text and kind == 'partial':
            logger.info('STT partial skipped: no text change')
            return
        last_text = text
        logger.info('STT sending transcript: kind=%s text_length=%s', kind, len(text))
        await _safe_send_json(websocket, {'type': kind, 'text': text})

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
                    partial_interval_ms = int(
                        payload.get('partialIntervalMs') or STT_PARTIAL_INTERVAL_MS
                    )
                    logger.info(
                        'STT start received: sample_rate=%s partial_interval_ms=%s',
                        sample_rate,
                        partial_interval_ms,
                    )
                    await stt_service.ensure_loaded()
                    continue
                if msg_type == 'stop':
                    stop_requested = True
                    logger.info('STT stop received: buffer_bytes=%s', len(audio_buffer))
                    if audio_buffer:
                        await emit_transcript('final')
                    else:
                        await _safe_send_json(websocket, {'type': 'final', 'text': ''})
                    break

            chunk = message.get('bytes')
            if chunk:
                audio_buffer.extend(chunk)
                min_bytes = int(sample_rate * 2 * (partial_interval_ms / 1000))
                logger.info(
                    'STT audio chunk received: chunk_bytes=%s total_bytes=%s threshold_bytes=%s',
                    len(chunk),
                    len(audio_buffer),
                    min_bytes,
                )
                if len(audio_buffer) - last_partial_audio_len >= min_bytes:
                    await emit_transcript('partial')
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
