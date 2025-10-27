import os
import shutil
import subprocess
import tempfile
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime

# --- FIX 1: Import BackgroundTask from Starlette ---
from starlette.background import BackgroundTask

from sqlalchemy.engine.url import make_url
from app.db.session import SessionLocal
from app.core.config import settings
from app.models.lead import Lead

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/package/{generation_no}", summary="Export Campaign as ZIP Package")
def export_campaign_package(generation_no: str, db: Session = Depends(get_db)):
    """
    Exports all leads and their corresponding audio files for a given
    generation_no into a single downloadable ZIP file.

    This package contains a database dump (.sql) and all associated audio.
    """
    leads = db.query(Lead).filter(Lead.generation_no == generation_no).all()
    if not leads:
        raise HTTPException(status_code=404, detail=f"No leads found for generation number: {generation_no}")

    campaign_name = leads[0].campaign_name

    with tempfile.TemporaryDirectory() as temp_dir:
        sql_dump_path = os.path.join(temp_dir, "leads_dump.sql")
        audio_dir = os.path.join(temp_dir, "audio")
        os.makedirs(audio_dir, exist_ok=True)
        
        try:
            db_url = make_url(settings.DATABASE_URL)
            pg_dump_command = [
                'pg_dump',
                '--data-only',
                '--inserts',
                '--table=leads',
                f'--dbname={db_url.database}',
                f'--host={db_url.host or "localhost"}',
                f'--port={str(db_url.port or 5432)}',
                f'--username={db_url.username}',
                f'--file={sql_dump_path}',
            ]
            
            env = os.environ.copy()
            if db_url.password:
                env['PGPASSWORD'] = db_url.password

            logger.info("Executing pg_dump command for 'leads' table...")
            result = subprocess.run(pg_dump_command, env=env, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"pg_dump failed. stderr: {result.stderr}")
                raise HTTPException(status_code=500, detail=f"Database dump failed: {result.stderr}")

            logger.info(f"Successfully created SQL dump at: {sql_dump_path}")

        except Exception as e:
            logger.error(f"An unexpected error occurred during pg_dump: {e}")
            raise HTTPException(status_code=500, detail=f"An unexpected error occurred during database dump: {e}")

        files_copied = 0
        for lead in leads:
            for filename in [lead.audio_filename_no_amd, lead.audio_filename_amd, lead.audio_filename_transfer, lead.audio_filename_voicemail]:
                if filename:
                    source_path = os.path.join(settings.AUDIO_STORAGE_PATH, filename)
                    dest_path = os.path.join(audio_dir, filename)
                    if os.path.exists(source_path):
                        shutil.copy2(source_path, dest_path)
                        files_copied += 1
        logger.info(f"Copied {files_copied} audio files to the package.")

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        safe_campaign_name = "".join(c for c in campaign_name if c.isalnum() or c in (' ', '_')).rstrip()
        zip_filename = f"{safe_campaign_name}_{generation_no}_{timestamp}.zip"
        
        zip_temp_path = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)

        shutil.make_archive(
            base_name=zip_temp_path,
            format='zip',
            root_dir=temp_dir
        )
        final_zip_path = f"{zip_temp_path}.zip"
        logger.info(f"Successfully created ZIP package at: {final_zip_path}")

        # --- FIX 2: Use BackgroundTask to safely schedule the file deletion ---
        # This guarantees the file is deleted ONLY AFTER the response is sent.
        cleanup_task = BackgroundTask(os.remove, final_zip_path)

        return FileResponse(
            path=final_zip_path,
            filename=zip_filename,
            media_type='application/zip',
            background=cleanup_task
        )