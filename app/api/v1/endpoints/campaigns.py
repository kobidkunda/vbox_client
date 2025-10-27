import pandas as pd
import io
import os
import random
import shutil
import numpy as np
import uuid
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from celery import group

# SessionLocal is now used directly in the endpoint
from app.db.session import SessionLocal
from app.api.v1 import schemas
from app.crud import lead as lead_crud
from app.worker.tasks import process_lead_audio
from app.core.config import settings

router = APIRouter()

# This dependency is still used for read-only endpoints like get_audio_for_vicidial
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/upload", response_model=schemas.CampaignUploadResponse, status_code=202)
async def upload_campaign_leads(
    *,
    # We remove the db: Session dependency here as we will manage it manually
    campaign_name: str = Form(...),
    generation_no: Optional[str] = Form(None),
    voice_group_id: str = Form(...),
    template_no_amd: str = Form(..., alias="no_amd_template"),
    template_amd: str = Form(..., alias="amd_template"),
    template_transfer: str = Form(...),
    template_voicemail: str = Form(""),
    llm_enabled: bool = Form(False),
    csv_file: UploadFile = File(...)
):
    if not template_no_amd or not template_no_amd.strip():
        raise HTTPException(status_code=400, detail="The 'Template (No AMD)' field cannot be empty.")
    if not template_amd or not template_amd.strip():
        raise HTTPException(status_code=400, detail="The 'Template (AMD Detected)' field cannot be empty.")

    # --- Start Manual DB Session for Voice Group Validation ---
    db = SessionLocal()
    try:
        group_uuid = uuid.UUID(voice_group_id)
        if not lead_crud.get_voice_group(db, group_uuid):
            raise HTTPException(status_code=404, detail="Selected voice group not found.")
        if not lead_crud.get_active_voices_by_group_id(db, group_uuid):
            raise HTTPException(status_code=400, detail="The selected voice group has no active voices.")
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid Voice Group ID format.")
    finally:
        db.close()
    # --- End Manual DB Session ---

    campaign_job_id = str(uuid.uuid4())

    if not csv_file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV.")

    try:
        contents = await csv_file.read()
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')), sep=',')
        df = df.replace(np.nan, None)
        column_map = {col.lower().strip(): col for col in df.columns}
        if 'phone' in column_map:
            df.rename(columns={column_map['phone']: 'phone'}, inplace=True)
        elif 'phone number' in column_map:
            df.rename(columns={column_map['phone number']: 'phone'}, inplace=True)
        else:
            raise HTTPException(status_code=400, detail="CSV file must contain a 'Phone' or 'Phone Number' column.")
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=400, detail=f"Error parsing CSV file: {e}")

    # --- DEFINITIVE FIX: Manual Session for Lead Creation ---
    db = SessionLocal()
    try:
        created_leads = lead_crud.bulk_create_leads(db=db, df=df, campaign_name=campaign_name, generation_no=generation_no)
        if not created_leads:
            raise HTTPException(status_code=400, detail="No valid leads found in the uploaded file.")
        
        # We need the IDs to send to Celery. The objects will expire once the session closes.
        lead_ids = [str(lead.id) for lead in created_leads]
        
        # Commit and close the session BEFORE dispatching tasks. This is the key.
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error during lead creation: {e}")
    finally:
        db.close()
    # --- End Manual Session ---

    lead_tasks = [
        process_lead_audio.s(
            lead_id=id, 
            template_no_amd=template_no_amd,
            template_amd=template_amd,
            template_transfer=template_transfer,
            template_voicemail=template_voicemail,
            llm_enabled=llm_enabled,
            voice_group_id=voice_group_id
        ) for id in lead_ids
    ]
    
    processing_group = group(lead_tasks)
    processing_group.apply_async()

    return {
        "job_id": campaign_job_id,
        "message": f"{len(lead_ids)} leads have been successfully queued for audio generation.",
        "total_leads": len(lead_ids)
    }

# --- Other endpoints remain the same and can still use the Depends(get_db) pattern ---

@router.get("/audio/{phone_number}", response_model=schemas.AudioResponse)
def get_audio_for_vicidial(phone_number: str, db: Session = Depends(get_db)):
    lead = lead_crud.get_lead_by_phone(db=db, phone_number=phone_number)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found for this phone number.")
    
    url_no_amd, url_amd, url_transfer, url_voicemail = None, None, None, None
    if lead.status == "COMPLETED":
        if lead.audio_filename_no_amd: url_no_amd = f"{settings.BASE_URL}/audio/{lead.audio_filename_no_amd}"
        if lead.audio_filename_amd: url_amd = f"{settings.BASE_URL}/audio/{lead.audio_filename_amd}"
        if lead.audio_filename_transfer: url_transfer = f"{settings.BASE_URL}/audio/{lead.audio_filename_transfer}"
        if lead.audio_filename_voicemail: url_voicemail = f"{settings.BASE_URL}/audio/{lead.audio_filename_voicemail}"
    
    return {"audio_url_no_amd": url_no_amd, "audio_url_amd": url_amd, "audio_url_transfer": url_transfer, "audio_url_voicemail": url_voicemail, "status": lead.status.value}

@router.post("/leads/delete", response_model=schemas.LeadActionResponse, tags=["Leads Actions"])
async def delete_leads(payload: schemas.LeadIdList, db: Session = Depends(get_db)):
    if not payload.lead_ids: raise HTTPException(status_code=400, detail="No lead IDs provided.")
    try:
        lead_uuids = [uuid.UUID(id_str) for id_str in payload.lead_ids]
    except ValueError:
        raise HTTPException(status_code=400, detail="One or more invalid lead IDs provided.")
    deleted_count = lead_crud.delete_leads_by_ids(db, lead_uuids)
    return {"success_count": deleted_count, "failed_count": len(lead_uuids) - deleted_count, "message": f"Successfully deleted {deleted_count} leads."}

@router.post("/voice-groups", response_model=schemas.VoiceGroup, tags=["Voice Management"])
def create_voice_group(group: schemas.VoiceGroupCreate, db: Session = Depends(get_db)):
    return lead_crud.create_voice_group(db, name=group.name, description=group.description)

@router.delete("/voice-groups/{group_id}", status_code=204, tags=["Voice Management"])
def delete_voice_group(group_id: uuid.UUID, db: Session = Depends(get_db)):
    if not lead_crud.delete_voice_group(db, group_id):
        raise HTTPException(status_code=404, detail="Voice group not found.")
    return

@router.post("/voices/upload", response_model=schemas.Voice, tags=["Voice Management"])
async def upload_voice_file(db: Session = Depends(get_db), voice_name: str = Form(...), group_id: uuid.UUID = Form(...), voice_file: UploadFile = File(...)):
    if voice_file.content_type not in ["audio/wav", "audio/mpeg", "audio/x-wav", "audio/mp3"]:
        raise HTTPException(status_code=400, detail=f"Invalid audio file type: {voice_file.content_type}.")
    if not lead_crud.get_voice_group(db, group_id):
        raise HTTPException(status_code=404, detail="Voice group not found.")
    safe_filename = f"{uuid.uuid4()}_{os.path.basename(voice_file.filename)}"
    file_path = os.path.join(settings.VOICE_STORAGE_PATH, safe_filename)
    with open(file_path, "wb") as buffer: shutil.copyfileobj(voice_file.file, buffer)
    return lead_crud.create_voice(db, name=voice_name, filename=safe_filename, filepath=file_path, group_id=group_id)

@router.post("/voices/{voice_id}/toggle", response_model=schemas.Voice, tags=["Voice Management"])
def toggle_voice(voice_id: uuid.UUID, db: Session = Depends(get_db)):
    voice = lead_crud.toggle_voice_active(db, voice_id)
    if not voice: raise HTTPException(status_code=404, detail="Voice not found.")
    return voice

@router.delete("/voices/{voice_id}", status_code=204, tags=["Voice Management"])
def delete_voice(voice_id: uuid.UUID, db: Session = Depends(get_db)):
    if not lead_crud.delete_voice(db, voice_id):
        raise HTTPException(status_code=404, detail="Voice not found.")
    return