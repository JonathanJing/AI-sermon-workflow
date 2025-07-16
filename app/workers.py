import logging
import time
from typing import Dict, Any
from datetime import datetime
from pathlib import Path
from app.models import TranscriptionJob, JobStatus, SourceType
from app.services.ingest.downloader import YouTubeDownloader
from app.services.ingest.audio_extractor import AudioExtractor
from app.services.stt.google_stt import GoogleSTTService
from app.services.subtitles.builder import SubtitleBuilder
from app.services.storage import storage_manager
from app.config import settings

logger = logging.getLogger(__name__)

# Service instances
youtube_downloader = YouTubeDownloader()
audio_extractor = AudioExtractor()
stt_service = GoogleSTTService()
subtitle_builder = SubtitleBuilder()

# Simple in-memory job storage (would be replaced with database in production)
job_storage: Dict[str, TranscriptionJob] = {}


def process_transcription_job(job_id: str):
    """
    Process a transcription job in the background
    
    Args:
        job_id: Unique job identifier
    """
    start_time = time.time()
    
    try:
        # Load job (in production, this would query the database)
        job = job_storage.get(job_id)
        if not job:
            logger.error(f"Job {job_id} not found in storage")
            return
        
        logger.info(f"Starting processing for job {job_id}")
        
        # Update job status
        job.status = JobStatus.IN_PROGRESS
        job.started_at = datetime.utcnow()
        
        # Step 1: Get/Process audio
        audio_file_path, audio_metadata = _get_audio_file(job)
        job.audio_file_path = audio_file_path
        job.duration_seconds = audio_metadata.get("duration_seconds")
        job.file_size_mb = audio_metadata.get("file_size_mb")
        job.title = job.title or audio_metadata.get("title")
        
        # Step 2: Check cost limits
        if job.duration_seconds:
            if not stt_service.check_cost_limit(job.duration_seconds):
                raise Exception(f"Estimated cost exceeds limit of ${settings.stt.cost_limit_usd}")
        
        # Step 3: Transcribe audio
        transcript_result, stt_metadata = stt_service.transcribe_audio(audio_file_path, job_id)
        job.transcript_path = stt_metadata.get("transcript_path")
        job.stt_cost_usd = stt_metadata.get("estimated_cost_usd")
        
        # Step 4: Generate subtitles
        srt_path, vtt_path, subtitle_metadata = subtitle_builder.create_subtitles(transcript_result, job_id)
        job.srt_path = srt_path
        job.vtt_path = vtt_path
        
        # Step 5: Save files to storage
        files_to_save = {
            "audio": audio_file_path,
            "transcript": job.transcript_path,
            "srt": srt_path,
            "vtt": vtt_path
        }
        
        storage_keys = storage_manager.save_job_files(job_id, files_to_save)
        
        # Update job with storage keys
        job.audio_file_path = storage_keys.get("audio")
        job.transcript_path = storage_keys.get("transcript")
        job.srt_path = storage_keys.get("srt")
        job.vtt_path = storage_keys.get("vtt")
        
        # Step 6: Update job status
        job.status = JobStatus.SUCCEEDED
        job.completed_at = datetime.utcnow()
        job.processing_time_seconds = time.time() - start_time
        
        logger.info(f"Job {job_id} completed successfully in {job.processing_time_seconds:.2f} seconds")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {str(e)}")
        
        # Update job with error
        if job_id in job_storage:
            job = job_storage[job_id]
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            job.processing_time_seconds = time.time() - start_time


def _get_audio_file(job: TranscriptionJob) -> tuple[str, Dict[str, Any]]:
    """
    Get audio file based on job source type
    Handles large files by splitting them into chunks if needed
    
    Args:
        job: Transcription job
        
    Returns:
        Tuple of (audio_file_path, metadata)
    """
    if job.source_type == SourceType.YOUTUBE:
        if not job.source_url:
            raise ValueError("YouTube URL is required")
        
        # Download from YouTube
        audio_file_path, metadata = youtube_downloader.download_audio(job.source_url, job.id)
        
        # Extract and process audio
        processed_audio_path, audio_metadata = audio_extractor.extract_from_file(audio_file_path, job.id)
        
        # Check if we need to split the audio for large files
        processed_path = Path(processed_audio_path)
        file_size_mb = processed_path.stat().st_size / (1024 * 1024)
        
        if file_size_mb > 9.0:  # If larger than 9MB, split it
            logger.info(f"Audio file is {file_size_mb:.2f}MB, splitting for job {job.id}")
            chunk_files = audio_extractor.split_audio_if_needed(processed_audio_path, job.id)
            
            if len(chunk_files) > 1:
                # Use the first chunk as the primary file path for STT processing
                # The STT service will automatically detect and process all chunks
                processed_audio_path = chunk_files[0]
                audio_metadata["chunks_created"] = len(chunk_files)
                audio_metadata["chunked_processing"] = True
                logger.info(f"Created {len(chunk_files)} chunks for job {job.id}")
        
        # Combine metadata
        combined_metadata = {**metadata, **audio_metadata}
        
        return processed_audio_path, combined_metadata
        
    elif job.source_type == SourceType.FILE:
        if not job.source_file_path:
            raise ValueError("File path is required")
        
        # Process local file
        audio_file_path, metadata = audio_extractor.extract_from_file(job.source_file_path, job.id)
        
        # Check if we need to split the audio for large files
        processed_path = Path(audio_file_path)
        file_size_mb = processed_path.stat().st_size / (1024 * 1024)
        
        if file_size_mb > 9.0:  # If larger than 9MB, split it
            logger.info(f"Audio file is {file_size_mb:.2f}MB, splitting for job {job.id}")
            chunk_files = audio_extractor.split_audio_if_needed(audio_file_path, job.id)
            
            if len(chunk_files) > 1:
                # Use the first chunk as the primary file path for STT processing
                audio_file_path = chunk_files[0]
                metadata["chunks_created"] = len(chunk_files)
                metadata["chunked_processing"] = True
                logger.info(f"Created {len(chunk_files)} chunks for job {job.id}")
        
        return audio_file_path, metadata
        
    else:
        raise ValueError(f"Unsupported source type: {job.source_type}")


def create_job(job: TranscriptionJob) -> str:
    """
    Create a new job in storage
    
    Args:
        job: Transcription job
        
    Returns:
        Job ID
    """
    job_storage[job.id] = job
    logger.info(f"Created job {job.id} in storage")
    return job.id


def get_job(job_id: str) -> TranscriptionJob:
    """
    Get job from storage
    
    Args:
        job_id: Job identifier
        
    Returns:
        Transcription job or None if not found
    """
    return job_storage.get(job_id)


def list_jobs(limit: int = 10, offset: int = 0, status: JobStatus = None) -> list:
    """
    List jobs from storage
    
    Args:
        limit: Maximum number of jobs
        offset: Number of jobs to skip
        status: Filter by status
        
    Returns:
        List of jobs
    """
    jobs = list(job_storage.values())
    
    # Filter by status if provided
    if status:
        jobs = [job for job in jobs if job.status == status]
    
    # Sort by creation time (newest first)
    jobs.sort(key=lambda x: x.created_at, reverse=True)
    
    # Apply pagination
    return jobs[offset:offset + limit]


def delete_job(job_id: str) -> bool:
    """
    Delete job from storage
    
    Args:
        job_id: Job identifier
        
    Returns:
        True if deleted, False if not found
    """
    if job_id in job_storage:
        del job_storage[job_id]
        logger.info(f"Deleted job {job_id} from storage")
        return True
    return False


def get_job_stats() -> Dict[str, Any]:
    """
    Get job statistics
    
    Returns:
        Dictionary with job statistics
    """
    jobs = list(job_storage.values())
    
    stats = {
        "total_jobs": len(jobs),
        "pending_jobs": len([j for j in jobs if j.status == JobStatus.PENDING]),
        "in_progress_jobs": len([j for j in jobs if j.status == JobStatus.IN_PROGRESS]),
        "completed_jobs": len([j for j in jobs if j.status == JobStatus.SUCCEEDED]),
        "failed_jobs": len([j for j in jobs if j.status == JobStatus.FAILED])
    }
    
    # Calculate average processing time for completed jobs
    completed_jobs = [j for j in jobs if j.status == JobStatus.SUCCEEDED and j.processing_time_seconds]
    if completed_jobs:
        avg_processing_time = sum(j.processing_time_seconds for j in completed_jobs) / len(completed_jobs)
        stats["average_processing_time_seconds"] = avg_processing_time
    
    # Calculate total cost
    total_cost = sum(j.stt_cost_usd for j in jobs if j.stt_cost_usd)
    stats["total_stt_cost_usd"] = total_cost
    
    return stats


def health_check() -> Dict[str, Any]:
    """
    Check worker health
    
    Returns:
        Health status
    """
    try:
        # Check service health
        stt_health = stt_service.health_check()
        storage_health = storage_manager.health_check()
        
        # Count active jobs
        active_jobs = len([j for j in job_storage.values() if j.status == JobStatus.IN_PROGRESS])
        
        return {
            "status": "healthy",
            "active_jobs": active_jobs,
            "total_jobs": len(job_storage),
            "services": {
                "stt": stt_health,
                "storage": storage_health
            }
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# Initialize job storage with some dummy data for testing
def _initialize_test_data():
    """Initialize some test data (for development only)"""
    if settings.debug:
        # Create a sample completed job
        test_job = TranscriptionJob(
            id="test-job-1",
            source_type=SourceType.FILE,
            source_file_path="test.mp3",
            title="Test Sermon",
            status=JobStatus.SUCCEEDED,
            duration_seconds=3600.0,
            file_size_mb=50.0,
            stt_cost_usd=2.50,
            processing_time_seconds=180.0
        )
        job_storage[test_job.id] = test_job
        
        logger.info("Initialized test data")


# Initialize test data when module is imported
_initialize_test_data() 