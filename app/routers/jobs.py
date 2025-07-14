import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime
from sqlmodel import Session, select
from app.models import (
    TranscriptionRequest, TranscriptionResponse, JobStatusResponse, 
    TranscriptionJob, JobStatus, SourceType, JobResults, ErrorResponse
)
from app.config import settings
from app.services.storage import storage_manager
from app.workers import process_transcription_job, create_job, get_job, list_jobs as list_jobs_worker, delete_job

router = APIRouter(prefix="/jobs", tags=["jobs"])
security = HTTPBearer(auto_error=False)

logger = logging.getLogger(__name__)


def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key if configured"""
    if settings.api.key:
        if not credentials or credentials.credentials != settings.api.key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials


@router.post("/transcribe", response_model=TranscriptionResponse)
async def create_transcription_job(
    background_tasks: BackgroundTasks,
    request: TranscriptionRequest,
    credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Create a new transcription job
    
    - **source_type**: "youtube" or "file"
    - **url**: YouTube URL (required if source_type is "youtube")
    - **file_path**: Path to local file (required if source_type is "file")
    - **title**: Optional title for the job
    - **metadata**: Optional additional metadata
    """
    try:
        # Validate request
        if request.source_type == SourceType.YOUTUBE:
            if not request.url:
                raise HTTPException(status_code=400, detail="URL is required for YouTube transcription")
        elif request.source_type == SourceType.FILE:
            if not request.file_path:
                raise HTTPException(status_code=400, detail="File path is required for file transcription")
        
        # Create job record
        job = TranscriptionJob(
            source_type=request.source_type,
            source_url=str(request.url) if request.url else None,
            source_file_path=request.file_path,
            title=request.title,
            metadata=request.metadata
        )
        
        # Save job to storage
        create_job(job)
        
        # Start background processing
        background_tasks.add_task(process_transcription_job, job.id)
        
        logger.info(f"Created transcription job {job.id} for {request.source_type}")
        
        return TranscriptionResponse(
            job_id=job.id,
            status=JobStatus.PENDING,
            message=f"Transcription job created successfully. Job ID: {job.id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create transcription job: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create transcription job: {str(e)}")


@router.post("/transcribe/upload", response_model=TranscriptionResponse)
async def upload_and_transcribe(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Upload a file and create transcription job
    
    - **file**: Audio/video file to transcribe
    - **title**: Optional title for the job
    """
    try:
        # Validate file type
        allowed_extensions = {'.mp3', '.mp4', '.wav', '.m4a', '.flac', '.webm'}
        file_extension = '.' + file.filename.split('.')[-1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: {file_extension}. Supported types: {', '.join(allowed_extensions)}"
            )
        
        # Save uploaded file
        upload_path = f"./data/raw/{file.filename}"
        with open(upload_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Create job
        job = TranscriptionJob(
            source_type=SourceType.FILE,
            source_file_path=upload_path,
            title=title or file.filename
        )
        
        # Save job to storage
        create_job(job)
        
        # Start background processing
        background_tasks.add_task(process_transcription_job, job.id)
        
        logger.info(f"Created transcription job {job.id} for uploaded file {file.filename}")
        
        return TranscriptionResponse(
            job_id=job.id,
            status=JobStatus.PENDING,
            message=f"File uploaded and transcription job created. Job ID: {job.id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload and transcribe: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload and transcribe: {str(e)}")


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Get job status and results
    
    - **job_id**: Unique job identifier
    """
    try:
        # Load job from storage
        job = get_job(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Build response
        response = JobStatusResponse(
            job_id=job.id,
            status=job.status,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            processing_time_seconds=job.processing_time_seconds,
            error_message=job.error_message
        )
        
        # Add results if job is completed
        if job.status == JobStatus.SUCCEEDED:
            # Get download URLs
            file_keys = {
                "audio": job.audio_file_path,
                "transcript": job.transcript_path,
                "srt": job.srt_path,
                "vtt": job.vtt_path
            }
            
            download_urls = storage_manager.get_job_file_urls(job_id, file_keys)
            
            response.results = JobResults(
                title=job.title,
                duration_seconds=job.duration_seconds,
                file_size_mb=job.file_size_mb,
                stt_cost_usd=job.stt_cost_usd,
                audio_download_url=download_urls.get("audio"),
                transcript_download_url=download_urls.get("transcript"),
                srt_download_url=download_urls.get("srt"),
                vtt_download_url=download_urls.get("vtt")
            )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")


@router.get("/", response_model=Dict[str, Any])
async def list_jobs(
    limit: int = 10,
    offset: int = 0,
    status: Optional[JobStatus] = None,
    credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    List transcription jobs
    
    - **limit**: Maximum number of jobs to return
    - **offset**: Number of jobs to skip
    - **status**: Filter by job status
    """
    try:
        # List jobs from storage
        jobs = list_jobs_worker(limit, offset, status)
        
        return {
            "jobs": jobs,
            "total": len(jobs),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Failed to list jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {str(e)}")


@router.delete("/{job_id}")
async def delete_job(
    job_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)
):
    """
    Delete a transcription job and its files
    
    - **job_id**: Unique job identifier
    """
    try:
        # Load job
        job = get_job(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Clean up files
        file_keys = {
            "audio": job.audio_file_path,
            "transcript": job.transcript_path,
            "srt": job.srt_path,
            "vtt": job.vtt_path
        }
        
        cleanup_results = storage_manager.cleanup_job_files(job_id, file_keys)
        
        # Delete job record
        delete_job(job_id)
        
        logger.info(f"Deleted job {job_id}")
        
        return {
            "message": "Job deleted successfully",
            "job_id": job_id,
            "cleanup_results": cleanup_results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete job: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete job: {str(e)}")


 