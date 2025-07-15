#!/usr/bin/env python3
"""
Test script for chunked WAV extraction from YouTube video
https://youtu.be/QBiaM7BXsY4

This test demonstrates the complete workflow:
1. Download audio from YouTube URL
2. Extract and process audio with chunking
3. Output chunked WAV files optimized for STT
"""

import sys
import uuid
import logging
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ingest.downloader import YouTubeDownloader
from app.services.ingest.audio_extractor import AudioExtractor
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_chunked_extraction():
    """Test chunked WAV extraction from YouTube video"""
    
    # Test configuration
    youtube_url = "https://youtu.be/QBiaM7BXsY4"
    job_id = str(uuid.uuid4())
    
    logger.info(f"Starting chunked extraction test for job: {job_id}")
    logger.info(f"YouTube URL: {youtube_url}")
    
    try:
        # Initialize services
        downloader = YouTubeDownloader()
        audio_extractor = AudioExtractor()
        
        # Step 1: Download audio from YouTube
        logger.info("Step 1: Downloading audio from YouTube...")
        raw_audio_path, video_metadata = downloader.download_audio(youtube_url, job_id)
        
        logger.info(f"Downloaded audio: {raw_audio_path}")
        logger.info(f"Video metadata: {video_metadata}")
        
        # Step 2: Extract and process audio
        logger.info("Step 2: Extracting and processing audio...")
        processed_audio_path, audio_metadata = audio_extractor.extract_from_file(raw_audio_path, job_id)
        
        logger.info(f"Processed audio: {processed_audio_path}")
        logger.info(f"Audio metadata: {audio_metadata}")
        
        # Step 3: Split audio into chunks if needed
        logger.info("Step 3: Splitting audio into chunks...")
        chunk_files = audio_extractor.split_audio_if_needed(processed_audio_path, job_id, max_chunk_size_mb=9.0)
        
        logger.info(f"Created {len(chunk_files)} chunks:")
        for i, chunk_file in enumerate(chunk_files):
            chunk_path = Path(chunk_file)
            chunk_size_mb = chunk_path.stat().st_size / (1024 * 1024)
            logger.info(f"  Chunk {i+1}: {chunk_file} ({chunk_size_mb:.2f} MB)")
        
        # Step 4: Verify chunk files
        logger.info("Step 4: Verifying chunk files...")
        for chunk_file in chunk_files:
            chunk_path = Path(chunk_file)
            if not chunk_path.exists():
                raise FileNotFoundError(f"Chunk file not found: {chunk_file}")
            
            # Verify audio can be loaded
            if not audio_extractor.validate_audio_file(chunk_file):
                raise ValueError(f"Invalid audio chunk: {chunk_file}")
        
        # Step 5: Display summary
        logger.info("Step 5: Summary")
        total_size_mb = sum(Path(f).stat().st_size for f in chunk_files) / (1024 * 1024)
        logger.info(f"Total chunks: {len(chunk_files)}")
        logger.info(f"Total size: {total_size_mb:.2f} MB")
        logger.info(f"Original duration: {audio_metadata.get('duration_seconds', 0):.1f} seconds")
        
        # List output files
        logger.info("Output files:")
        for chunk_file in chunk_files:
            logger.info(f"  {chunk_file}")
        
        return {
            "job_id": job_id,
            "youtube_url": youtube_url,
            "video_metadata": video_metadata,
            "audio_metadata": audio_metadata,
            "chunk_files": chunk_files,
            "total_chunks": len(chunk_files),
            "total_size_mb": total_size_mb,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        return {
            "job_id": job_id,
            "youtube_url": youtube_url,
            "error": str(e),
            "status": "failed"
        }


def test_video_info():
    """Test getting video information without downloading"""
    
    youtube_url = "https://youtu.be/QBiaM7BXsY4"
    
    logger.info(f"Getting video info for: {youtube_url}")
    
    try:
        downloader = YouTubeDownloader()
        video_info = downloader.get_video_info(youtube_url)
        
        logger.info("Video Information:")
        logger.info(f"  Title: {video_info.get('title', 'N/A')}")
        logger.info(f"  Author: {video_info.get('author', 'N/A')}")
        logger.info(f"  Duration: {video_info.get('length', 0)} seconds")
        logger.info(f"  Views: {video_info.get('views', 0):,}")
        logger.info(f"  Upload Date: {video_info.get('publish_date', 'N/A')}")
        
        return video_info
        
    except Exception as e:
        logger.error(f"Failed to get video info: {str(e)}")
        return None


def clean_test_files(job_id: str, preserve_wav: bool = True):
    """Clean up test files"""
    
    logger.info(f"Cleaning up test files for job: {job_id}")
    
    try:
        # Clean up raw files (non-WAV)
        raw_path = Path(settings.storage.local_path) / "raw"
        for file in raw_path.glob(f"{job_id}*"):
            if not preserve_wav or not file.suffix.lower() == '.wav':
                file.unlink()
                logger.info(f"Deleted raw file: {file}")
            else:
                logger.info(f"Preserved WAV file: {file}")
        
        # Clean up processed files (preserve WAV chunks)
        processed_path = Path(settings.storage.local_path) / "processed"
        for file in processed_path.glob(f"{job_id}*"):
            if not preserve_wav or not file.suffix.lower() == '.wav':
                file.unlink()
                logger.info(f"Deleted processed file: {file}")
            else:
                logger.info(f"Preserved WAV file: {file}")
        
        logger.info("Cleanup completed")
        
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test chunked WAV extraction from YouTube")
    parser.add_argument("--info-only", action="store_true", help="Only get video info, don't download")
    parser.add_argument("--no-cleanup", action="store_true", help="Keep all files (WAV files are preserved by default)")
    parser.add_argument("--full-cleanup", action="store_true", help="Delete all files including WAV files")
    
    args = parser.parse_args()
    
    if args.info_only:
        # Only get video information
        video_info = test_video_info()
        if video_info:
            logger.info("Video info test completed successfully")
        else:
            logger.error("Video info test failed")
            sys.exit(1)
    else:
        # Full extraction test
        result = test_chunked_extraction()
        
        if result["status"] == "success":
            logger.info("Chunked extraction test completed successfully!")
            logger.info(f"Generated {result['total_chunks']} chunks totaling {result['total_size_mb']:.2f} MB")
            
            # Handle cleanup options
            if args.full_cleanup:
                logger.info("Performing full cleanup (including WAV files)...")
                clean_test_files(result["job_id"], preserve_wav=False)
            elif not args.no_cleanup:
                logger.info("Performing partial cleanup (preserving WAV files)...")
                clean_test_files(result["job_id"], preserve_wav=True)
            else:
                logger.info("Skipping cleanup - all files preserved.")
        else:
            logger.error("Chunked extraction test failed!")
            logger.error(f"Error: {result.get('error', 'Unknown error')}")
            sys.exit(1)