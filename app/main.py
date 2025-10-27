from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.v1.endpoints import frontend, vicidial, importer
from app.core.config import settings
import os

app = FastAPI(title="Vicidial Playback Service")

# Create storage directories if they don't exist
os.makedirs(settings.AUDIO_STORAGE_PATH, exist_ok=True)

# Mount the local audio directory
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/audio", StaticFiles(directory=settings.AUDIO_STORAGE_PATH), name="audio")

# Include only the necessary routers
app.include_router(frontend.router, tags=["Frontend GUI"])
app.include_router(vicidial.router, prefix="/api/v1/vicidial", tags=["Vicidial API"])
app.include_router(importer.router, prefix="/api/v1/importer", tags=["Campaign Importer API"])
