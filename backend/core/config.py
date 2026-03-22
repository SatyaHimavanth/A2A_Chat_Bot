import os

from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}

AGENT_STATUS_CHECK_TIMEOUT_SECONDS = float(
    os.getenv('AGENT_STATUS_CHECK_TIMEOUT_SECONDS', '12')
)
AGENT_STATUS_CACHE_TTL_SECONDS = int(os.getenv('AGENT_STATUS_CACHE_TTL_SECONDS', '30'))
SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-production')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '120'))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS', '30'))
STREAM_CONNECT_TIMEOUT_SECONDS = float(os.getenv('STREAM_CONNECT_TIMEOUT_SECONDS', '60'))
STREAM_READ_TIMEOUT_SECONDS = float(os.getenv('STREAM_READ_TIMEOUT_SECONDS', '240'))
STT_MODEL_ID = os.getenv('STT_MODEL_ID', 'ibm-granite/granite-4.0-1b-speech')
STT_MODELS_DIR = os.getenv('STT_MODELS_DIR', './models')
STT_TARGET_SAMPLE_RATE = int(os.getenv('STT_TARGET_SAMPLE_RATE', '16000'))
STT_PARTIAL_INTERVAL_MS = int(os.getenv('STT_PARTIAL_INTERVAL_MS', '1500'))
STT_DEFAULT_PAUSE_MS = int(os.getenv('STT_DEFAULT_PAUSE_MS', '1600'))
STT_PARTIAL_WINDOW_SECONDS = float(os.getenv('STT_PARTIAL_WINDOW_SECONDS', '8'))
STT_SILENCE_RMS_THRESHOLD = float(os.getenv('STT_SILENCE_RMS_THRESHOLD', '0.012'))
STT_ENDPOINT_SILENCE_MS = int(os.getenv('STT_ENDPOINT_SILENCE_MS', '1200'))
STT_NOISE_GATE_THRESHOLD = float(os.getenv('STT_NOISE_GATE_THRESHOLD', '0.015'))
STT_MIN_VOICED_RATIO = float(os.getenv('STT_MIN_VOICED_RATIO', '0.08'))
STT_PRELOAD_ON_STARTUP = _as_bool(os.getenv('STT_PRELOAD_ON_STARTUP', 'true'), True)
HF_TOKEN = os.getenv('HF_TOKEN', '').strip()
STT_WHISPER_TASK = os.getenv('STT_WHISPER_TASK', 'translate').strip().lower()
STT_WHISPER_SOURCE_LANGUAGE = os.getenv('STT_WHISPER_SOURCE_LANGUAGE', '').strip().lower()
STT_MAX_NEW_TOKENS = int(os.getenv('STT_MAX_NEW_TOKENS', '512'))
