from pydantic import BaseModel, Field
from typing import Optional, List
import uuid

class CampaignUploadResponse(BaseModel):
    job_id: str
    message: str
    total_leads: int

class AudioResponse(BaseModel):
    audio_url_no_amd: Optional[str] = None
    audio_url_amd: Optional[str] = None
    audio_url_transfer: Optional[str] = None
    audio_url_voicemail: Optional[str] = None
    status: str

class LeadStatusResponse(BaseModel):
    id: uuid.UUID
    phone_number: str
    status: str
    audio_filename_no_amd: Optional[str] = None
    audio_filename_amd: Optional[str] = None
    audio_filename_transfer: Optional[str] = None
    audio_filename_voicemail: Optional[str] = None
    generation_no: Optional[str] = None

    class Config:
        from_attributes = True

class VoiceBase(BaseModel):
    name: str
    is_active: bool = True

class Voice(VoiceBase):
    id: uuid.UUID
    filename: str

    class Config:
        from_attributes = True

class VoiceGroupBase(BaseModel):
    name: str
    description: Optional[str] = None

class VoiceGroupCreate(VoiceGroupBase):
    pass

class VoiceGroup(VoiceGroupBase):
    id: uuid.UUID
    voices: List[Voice] = []

    class Config:
        from_attributes = True
        
class LeadIdList(BaseModel):
    lead_ids: List[str]

class LeadActionResponse(BaseModel):
    success_count: int
    failed_count: int
    message: str

# --- NEW SCHEMAS FOR VICIDIAL API ---

class RandomAudioResponse(BaseModel):
    """
    Response for the first call to get a random lead.
    It includes the URL for the first audio file and the key to use for subsequent calls.
    """
    audio_url: Optional[str]
    lead_key: str

class SpecificAudioResponse(BaseModel):
    """
    Response for subsequent calls for a specific lead.
    It only needs to return the requested audio URL.
    """
    audio_url: Optional[str]