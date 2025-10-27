import os
import shutil
import tempfile
import logging
import zipfile
import csv
import json
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import SessionLocal
from app.core.config import settings
from app.models.lead import Lead, LeadStatus

router = APIRouter()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/upload", summary="Import and Deploy Campaign Package")
async def import_campaign_package(db: Session = Depends(get_db), package: UploadFile = File(...)):
    if not package.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a .zip package.")

    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, "package.zip")
        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(package.file, buffer)

        logger.info("Extracting campaign package...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        csv_dump_path = os.path.join(temp_dir, "leads.csv")
        extracted_audio_dir = os.path.join(temp_dir, "audio")

        if not os.path.exists(csv_dump_path):
            raise HTTPException(status_code=400, detail="Package is invalid: leads.csv not found.")

        try:
            logger.info("Wiping existing leads and audio files...")
            db.execute(text('TRUNCATE TABLE leads RESTART IDENTITY'))
            db.commit()

            audio_path = settings.AUDIO_STORAGE_PATH
            if os.path.isdir(audio_path):
                shutil.rmtree(audio_path)
            os.makedirs(audio_path, exist_ok=True)
            
            logger.info("Importing new leads from CSV file...")
            leads_to_create = []
            with open(csv_dump_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    new_lead = Lead(
                        id=uuid.UUID(row['id']),
                        phone_number=row['phone_number'],
                        campaign_name=row['campaign_name'],
                        generation_no=row.get('generation_no') or None,
                        lead_data=json.loads(row['lead_data']),
                        status=LeadStatus(row['status']),
                        audio_filename_no_amd=row.get('audio_filename_no_amd') or None,
                        audio_filename_amd=row.get('audio_filename_amd') or None,
                        audio_filename_transfer=row.get('audio_filename_transfer') or None,
                        audio_filename_voicemail=row.get('audio_filename_voicemail') or None,
                        llm_input_no_amd=row.get('llm_input_no_amd') or None,
                        llm_output_no_amd=row.get('llm_output_no_amd') or None,
                        llm_input_amd=row.get('llm_input_amd') or None,
                        llm_output_amd=row.get('llm_output_amd') or None,
                        llm_input_transfer=row.get('llm_input_transfer') or None,
                        llm_output_transfer=row.get('llm_output_transfer') or None,
                        llm_input_voicemail=row.get('llm_input_voicemail') or None,
                        llm_output_voicemail=row.get('llm_output_voicemail') or None,
                        created_at=row.get('created_at') or None,
                        updated_at=row.get('updated_at') or None
                    )
                    leads_to_create.append(new_lead)
            
            if leads_to_create:
                db.add_all(leads_to_create)
                db.commit()
            
            lead_count = len(leads_to_create)
            logger.info(f"VERIFICATION: Successfully created {lead_count} leads in the database.")

            # --- FIX: Use a more compatible method for copying files that works in Python 3.6 ---
            logger.info("Moving new audio files into place...")
            if os.path.isdir(extracted_audio_dir):
                for filename in os.listdir(extracted_audio_dir):
                    source_file = os.path.join(extracted_audio_dir, filename)
                    destination_file = os.path.join(audio_path, filename)
                    shutil.copy2(source_file, destination_file) # copy2 is a robust copy command
            logger.info("Audio files successfully moved.")

        except Exception as e:
            db.rollback()
            logger.error(f"A critical error occurred during import: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    return {"message": f"Campaign package imported. Verified {lead_count} leads in the database."}