import os
import uuid
import pandas as pd
from sqlalchemy.orm import Session, joinedload
# --- NEW: Import func for random ordering ---
from sqlalchemy import func
# --- FIX: Import LeadStatus for filtering ---
from app.models.lead import Lead, Voice, VoiceGroup, LeadStatus
from app.core.config import settings
from typing import List, Optional

# --- LEAD CRUD Functions ---

def bulk_create_leads(db: Session, df: pd.DataFrame, campaign_name: str, generation_no: Optional[str]) -> List[Lead]:
    df['phone'] = df['phone'].astype(str)
    df.drop_duplicates(subset=['phone'], keep='last', inplace=True)
    phone_numbers = df['phone'].tolist()
    if phone_numbers:
        db.query(Lead).filter(Lead.phone_number.in_(phone_numbers)).delete(synchronize_session='fetch')
    leads_to_create = []
    for _, row in df.iterrows():
        lead_data = row.to_dict()
        phone_number = lead_data.pop('phone', None)
        if phone_number:
            db_lead = Lead(
                phone_number=phone_number,
                campaign_name=campaign_name,
                generation_no=generation_no,
                lead_data=lead_data
            )
            leads_to_create.append(db_lead)
    db.add_all(leads_to_create)
    db.flush()
    return leads_to_create

def get_lead_by_phone(db: Session, phone_number: str):
    return db.query(Lead).filter(Lead.phone_number == phone_number).first()

# --- NEW FUNCTION FOR VICIDIAL API ---
def get_random_completed_lead_by_generation(db: Session, generation_no: str) -> Optional[Lead]:
    """
    Selects a single, random lead from the database that is completed and
    matches the given generation number. This is highly efficient.
    """
    return db.query(Lead).filter(
        Lead.generation_no == generation_no,
        Lead.status == LeadStatus.COMPLETED
    ).order_by(func.random()).first()

def get_leads(db: Session, skip: int = 0, limit: int = 100) -> List[Lead]:
    return db.query(Lead).order_by(Lead.created_at.desc()).offset(skip).limit(limit).all()

def get_leads_by_ids(db: Session, lead_ids: List[uuid.UUID]) -> List[Lead]:
    return db.query(Lead).filter(Lead.id.in_(lead_ids)).all()

def delete_leads_by_ids(db: Session, lead_ids: List[uuid.UUID]) -> int:
    leads_to_delete = db.query(Lead).filter(Lead.id.in_(lead_ids)).all()
    for lead in leads_to_delete:
        for filename in [lead.audio_filename_no_amd, lead.audio_filename_amd, lead.audio_filename_transfer, lead.audio_filename_voicemail]:
            if filename:
                try:
                    file_path = os.path.join(settings.AUDIO_STORAGE_PATH, filename)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except OSError:
                    pass
    num_deleted = db.query(Lead).filter(Lead.id.in_(lead_ids)).delete(synchronize_session=False)
    db.commit()
    return num_deleted

def create_voice_group(db: Session, name: str, description: Optional[str]) -> VoiceGroup:
    db_group = VoiceGroup(name=name, description=description)
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

def get_voice_group(db: Session, group_id: uuid.UUID) -> Optional[VoiceGroup]:
    return db.query(VoiceGroup).filter(VoiceGroup.id == group_id).first()

def get_all_voice_groups(db: Session) -> List[VoiceGroup]:
    return db.query(VoiceGroup).order_by(VoiceGroup.name).all()

def get_all_voice_groups_with_voices(db: Session) -> List[VoiceGroup]:
    return db.query(VoiceGroup).options(joinedload(VoiceGroup.voices)).order_by(VoiceGroup.name).all()

def delete_voice_group(db: Session, group_id: uuid.UUID) -> Optional[VoiceGroup]:
    group = db.query(VoiceGroup).filter(VoiceGroup.id == group_id).first()
    if group:
        db.delete(group)
        db.commit()
    return group

def create_voice(db: Session, name: str, filename: str, filepath: str, group_id: uuid.UUID) -> Voice:
    db_voice = Voice(name=name, filename=filename, filepath=filepath, group_id=group_id)
    db.add(db_voice)
    db.commit()
    db.refresh(db_voice)
    return db_voice

def get_voice(db: Session, voice_id: uuid.UUID) -> Optional[Voice]:
    return db.query(Voice).filter(Voice.id == voice_id).first()

def delete_voice(db: Session, voice_id: uuid.UUID) -> Optional[Voice]:
    voice = db.query(Voice).filter(Voice.id == voice_id).first()
    if voice:
        try:
            if os.path.exists(voice.filepath):
                os.remove(voice.filepath)
        except OSError:
            pass
        db.delete(voice)
        db.commit()
    return voice

def toggle_voice_active(db: Session, voice_id: uuid.UUID) -> Optional[Voice]:
    voice = db.query(Voice).filter(Voice.id == voice_id).first()
    if voice:
        voice.is_active = not voice.is_active
        db.commit()
        db.refresh(voice)
    return voice

def get_active_voices_by_group_id(db: Session, group_id: uuid.UUID) -> List[Voice]:
    return db.query(Voice).filter(Voice.group_id == group_id, Voice.is_active == True).all()