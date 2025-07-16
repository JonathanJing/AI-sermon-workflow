from sqlmodel import SQLModel, Field, Column, DateTime, Text
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class JobStatus(str, Enum):
    """Job status enumeration"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SourceType(str, Enum):
    """Source type enumeration"""
    YOUTUBE = "youtube"
    FILE = "file"


class TranscriptionJob(SQLModel, table=True):
    """Database model for transcription jobs"""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    status: JobStatus = Field(default=JobStatus.PENDING)
    source_type: SourceType
    source_url: Optional[str] = None
    source_file_path: Optional[str] = None
    
    # Results
    audio_file_path: Optional[str] = None
    transcript_path: Optional[str] = None
    srt_path: Optional[str] = None
    vtt_path: Optional[str] = None
    
    # Metadata
    title: Optional[str] = None
    duration_seconds: Optional[float] = None
    file_size_mb: Optional[float] = None
    
    # Processing info
    processing_time_seconds: Optional[float] = None
    stt_cost_usd: Optional[float] = None
    error_message: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Additional metadata
    job_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(Text))


class TranscriptionRequest(BaseModel):
    """Request model for transcription"""
    source_type: SourceType
    url: Optional[HttpUrl] = None
    file_path: Optional[str] = None
    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TranscriptionResponse(BaseModel):
    """Response model for transcription job creation"""
    job_id: str
    status: JobStatus
    message: str


class JobStatusResponse(BaseModel):
    """Response model for job status"""
    job_id: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_seconds: Optional[float] = None
    error_message: Optional[str] = None
    
    # Results (only populated when completed)
    results: Optional["JobResults"] = None


class JobResults(BaseModel):
    """Job results model"""
    title: Optional[str] = None
    duration_seconds: Optional[float] = None
    file_size_mb: Optional[float] = None
    stt_cost_usd: Optional[float] = None
    
    # Download URLs
    audio_download_url: Optional[str] = None
    transcript_download_url: Optional[str] = None
    srt_download_url: Optional[str] = None
    vtt_download_url: Optional[str] = None


class TranscriptEntry(BaseModel):
    """Individual transcript entry"""
    start_time: float
    end_time: float
    text: str
    confidence: Optional[float] = None
    speaker: Optional[str] = None


class TranscriptResult(BaseModel):
    """Complete transcript result"""
    entries: List[TranscriptEntry]
    total_duration: float
    language: str
    confidence: Optional[float] = None


class SubtitleEntry(BaseModel):
    """Individual subtitle entry"""
    start_time: float
    end_time: float
    text: str
    position: Optional[int] = None


class ProcessingMetrics(BaseModel):
    """Processing metrics model"""
    audio_extraction_time: Optional[float] = None
    stt_processing_time: Optional[float] = None
    subtitle_generation_time: Optional[float] = None
    total_processing_time: Optional[float] = None
    stt_cost_estimate: Optional[float] = None
    file_size_mb: Optional[float] = None
    audio_duration_seconds: Optional[float] = None


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str
    version: str
    timestamp: datetime
    dependencies: Dict[str, str]  # service_name -> status


# Update forward references
JobStatusResponse.model_rebuild() 