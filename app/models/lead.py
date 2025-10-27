import uuid
from sqlalchemy import Column, String, JSON, DateTime, func, Enum as SQLAlchemyEnum, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from enum import Enum as PythonEnum

Base = declarative_base()

class LeadStatus(str, PythonEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Lead(Base):
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_number = Column(String, nullable=False, unique=True, index=True)
    campaign_name = Column(String, index=True)
    generation_no = Column(String, index=True, nullable=True)
    lead_data = Column(JSON, nullable=False)
    
    status = Column(SQLAlchemyEnum(LeadStatus), nullable=False, default=LeadStatus.PENDING)
    
    audio_filename_no_amd = Column(String, nullable=True)
    audio_filename_amd = Column(String, nullable=True)
    audio_filename_transfer = Column(String, nullable=True)
    audio_filename_voicemail = Column(String, nullable=True)
    
    llm_input_no_amd = Column(Text, nullable=True)
    llm_output_no_amd = Column(Text, nullable=True)
    llm_input_amd = Column(Text, nullable=True)
    llm_output_amd = Column(Text, nullable=True)
    llm_input_transfer = Column(Text, nullable=True)
    llm_output_transfer = Column(Text, nullable=True)
    llm_input_voicemail = Column(Text, nullable=True)
    llm_output_voicemail = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class VoiceGroup(Base):
    __tablename__ = "voice_groups"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    voices = relationship("Voice", back_populates="group", cascade="all, delete-orphan")

class Voice(Base):
    __tablename__ = "voices"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    filename = Column(String, nullable=False, unique=True)
    filepath = Column(String, nullable=False, unique=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    group_id = Column(UUID(as_uuid=True), ForeignKey("voice_groups.id"), nullable=False)
    group = relationship("VoiceGroup", back_populates="voices")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())