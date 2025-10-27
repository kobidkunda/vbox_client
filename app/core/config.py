import os
# --- FIX: Import BaseSettings from the main pydantic library ---
# Your installed version of FastAPI depends on an older Pydantic version (1.x)
# where BaseSettings is located in the core pydantic package.
from pydantic import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    AUDIO_STORAGE_PATH: str
    VOICE_STORAGE_PATH: str
    BASE_URL: str
    TTS_SERVICE_URL: str

    class Config:
        env_file = ".env"

settings = Settings()

# This part remains the same
os.makedirs(settings.AUDIO_STORAGE_PATH, exist_ok=True)
os.makedirs(settings.VOICE_STORAGE_PATH, exist_ok=True)