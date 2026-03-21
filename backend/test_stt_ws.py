import asyncio
from datetime import datetime
import json
from pathlib import Path
import subprocess

import httpx
import websockets


BACKEND_BASE_URL = 'http://127.0.0.1:8000'
WS_BASE_URL = 'ws://127.0.0.1:8000'
USERNAME = 'admin'
PASSWORD = 'admin'
TARGET_SAMPLE_RATE = 16000
CHUNK_SAMPLES = 3200
PARTIAL_INTERVAL_MS = 30000
FINAL_WAIT_TIMEOUT_SECONDS = 300
SAMPLE_WAV = Path(
    'models/ibm-granite--granite-4.0-1b-speech/multilingual_sample.wav'
)


def log(message: str) -> None:
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f'[{timestamp}] {message}')


async def fetch_access_token() -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f'{BACKEND_BASE_URL}/api/login',
            json={'username': USERNAME, 'password': PASSWORD},
        )
        response.raise_for_status()
        payload = response.json()
        return payload['access_token']


def load_pcm16_chunks() -> list[bytes]:
    command = [
        'ffmpeg',
        '-v',
        'error',
        '-i',
        str(SAMPLE_WAV),
        '-f',
        's16le',
        '-acodec',
        'pcm_s16le',
        '-ac',
        '1',
        '-ar',
        str(TARGET_SAMPLE_RATE),
        '-',
    ]
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
    )
    pcm16 = result.stdout
    if not pcm16:
        raise RuntimeError('ffmpeg returned empty PCM output for sample wav.')
    chunk_size = CHUNK_SAMPLES * 2
    return [pcm16[i : i + chunk_size] for i in range(0, len(pcm16), chunk_size)]


async def main() -> None:
    if not SAMPLE_WAV.exists():
        raise FileNotFoundError(f'Sample WAV not found: {SAMPLE_WAV}')

    token = await fetch_access_token()
    chunks = load_pcm16_chunks()
    ws_url = f'{WS_BASE_URL}/api/stt/ws?token={token}'

    log(f'Connecting to {ws_url}')
    async with websockets.connect(
        ws_url,
        max_size=8 * 1024 * 1024,
        ping_interval=None,
        ping_timeout=None,
        close_timeout=60,
    ) as websocket:
        ready_msg = await websocket.recv()
        log(f'READY: {ready_msg}')

        await websocket.send(
            json.dumps(
                {
                    'type': 'start',
                    'sampleRate': TARGET_SAMPLE_RATE,
                    'partialIntervalMs': PARTIAL_INTERVAL_MS,
                }
            )
        )
        log(
            f'Streaming {len(chunks)} audio chunks from {SAMPLE_WAV} '
            f'with partialIntervalMs={PARTIAL_INTERVAL_MS}'
        )

        async def receive_messages() -> None:
            try:
                while True:
                    message = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=FINAL_WAIT_TIMEOUT_SECONDS,
                    )
                    log(f'RECV: {message}')
            except asyncio.TimeoutError:
                log(
                    f'Timed out waiting {FINAL_WAIT_TIMEOUT_SECONDS}s for more websocket messages.'
                )
            except websockets.ConnectionClosed:
                log('Websocket closed by server.')

        receiver_task = asyncio.create_task(receive_messages())

        for index, chunk in enumerate(chunks, start=1):
            await websocket.send(chunk)
            log(f'SENT chunk {index}/{len(chunks)} bytes={len(chunk)}')
            await asyncio.sleep(0.05)

        await websocket.send(json.dumps({'type': 'stop'}))
        log('SENT stop')

        await receiver_task


if __name__ == '__main__':
    asyncio.run(main())
