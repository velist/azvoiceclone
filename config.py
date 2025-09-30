import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / "siliconflowkey.env"


def _load_env() -> None:
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=True)
    else:
        load_dotenv(override=True)


def get_api_key() -> str:
    _load_env()
    return os.getenv("API_KEY", "").strip()


API_URL = "https://api.siliconflow.cn/v1/audio/speech"
VOICE_UPLOAD_URL = "https://api.siliconflow.cn/v1/uploads/audio/voice"
MODEL_NAME = "IndexTeam/IndexTTS-2"


APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "7860"))
APP_SHARE = False

ACTIVATION_STORE_PATH = BASE_DIR / "activation_codes.json"


DEFAULT_SPEED = 1.0
DEFAULT_PITCH = 1.0
DEFAULT_VOLUME = 1.0




def get_admin_password() -> str:
    _load_env()
    return os.getenv("ADMIN_PASSWORD", "admin123").strip()

SUPPORTED_AUDIO_FORMATS = ["mp3", "wav", "ogg", "flac"]
