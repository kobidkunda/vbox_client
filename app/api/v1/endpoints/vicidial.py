from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import SessionLocal
from app.api.v1 import schemas
from app.crud import lead as lead_crud
from app.core.config import settings
from app.models.lead import Lead

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _get_audio_url_for_lead(lead: Lead, audio_type: str) -> Optional[str]:
    """Helper function to get the correct audio URL based on audio_type."""
    filename_map = {
        "no_amd": lead.audio_filename_no_amd,
        "amd": lead.audio_filename_amd,
        "transfer": lead.audio_filename_transfer,
        "voicemail": lead.audio_filename_voicemail,
    }
    filename = filename_map.get(audio_type.lower())
    if filename:
        return f"{settings.BASE_URL}/audio/{filename}"
    return None

@router.get(
    "/random_audio/{generation_no}/{audio_type}",
    response_model=schemas.RandomAudioResponse,
    summary="Get Random Lead Audio for a Generation"
)
def get_random_audio(
    generation_no: str,
    audio_type: str,
    db: Session = Depends(get_db)
):
    """
    Called once at the start of a Vicidial call.

    - Finds a random, completed lead for the specified **generation_no**.
    - Returns the URL for the requested **audio_type** and a **lead_key**.
    - The **lead_key** (phone number) MUST be stored by Vicidial in a channel
      variable to be used for subsequent requests for the same call.
    """
    lead = lead_crud.get_random_completed_lead_by_generation(db, generation_no=generation_no)
    
    if not lead:
        raise HTTPException(status_code=404, detail=f"No completed leads found for generation number: {generation_no}")

    audio_url = _get_audio_url_for_lead(lead, audio_type)

    return {
        "audio_url": audio_url,
        "lead_key": lead.phone_number
    }

@router.get(
    "/specific_audio/{lead_key}/{audio_type}",
    response_model=schemas.SpecificAudioResponse,
    summary="Get Specific Lead Audio by Key"
)
def get_specific_audio(
    lead_key: str,
    audio_type: str,
    db: Session = Depends(get_db)
):
    """
    Called for all subsequent audio requests during a single Vicidial call.

    - Uses the **lead_key** (the phone number) from the first API call to find the exact lead.
    - Returns the URL for the new requested **audio_type**.
    """
    lead = lead_crud.get_lead_by_phone(db, phone_number=lead_key)

    if not lead:
        raise HTTPException(status_code=404, detail=f"No lead found for key: {lead_key}")

    audio_url = _get_audio_url_for_lead(lead, audio_type)

    return {
        "audio_url": audio_url
    }