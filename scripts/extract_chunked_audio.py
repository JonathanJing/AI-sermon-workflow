#!/usr/bin/env python3
"""
Script to extract chunked WAV files from YouTube video
https://youtu.be/QBiaM7BXsY4

Usage:
    python scripts/extract_chunked_audio.py --url https://youtu.be/QBiaM7BXsY4 --job-id test-job
    python scripts/extract_chunked_audio.py --url https://youtu.be/QBiaM7BXsY4 --chunk-size 5.0
"""

import sys
import uuid
import logging
import argparse
from pathlib import Path
from typing import Optional

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ingest.downloader import YouTubeDownloader
from app.services.ingest.audio_extractor import AudioExtractor
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_chunked_audio(
    youtube_url: str,
    job_id: Optional[str] = None,
    chunk_size_mb: float = 9.0,
    output_dir: Optional[str] = None
):
    """
    Extract chunked WAV files from YouTube video
    
    Args:
        youtube_url: YouTube video URL
        job_id: Optional job identifier (will generate UUID if not provided)
        chunk_size_mb: Maximum chunk size in MB
        output_dir: Optional output directory (uses default if not provided)
    
    Returns:
        List of chunk file paths
    """
    
    # Generate job ID if not provided
    if not job_id:
        job_id = str(uuid.uuid4())[:8]
    
    # Set output directory if provided
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        # Temporarily override the settings
        original_path = settings.local_storage_path
        settings.local_storage_path = str(output_path)
    
    logger.info(f"Job ID: {job_id}")
    logger.info(f"YouTube URL: {youtube_url}")
    logger.info(f"Max chunk size: {chunk_size_mb} MB")
    
    try:
        # Initialize services
        downloader = YouTubeDownloader()
        audio_extractor = AudioExtractor()
        
        # Step 1: Validate URL
        logger.info("Validating YouTube URL...")
        if not downloader.validate_url(youtube_url):
            raise ValueError(f"Invalid YouTube URL: {youtube_url}")
        
        # Step 2: Get video info
        logger.info("Getting video information...")
        video_info = downloader.get_video_info(youtube_url)
        
        logger.info(f"Video: {video_info.get('title', 'Unknown')}")
        logger.info(f"Author: {video_info.get('author', 'Unknown')}")
        logger.info(f"Duration: {video_info.get('length', 0)} seconds ({video_info.get('length', 0)/60:.1f} minutes)")
        
        # Step 3: Download audio
        logger.info("Downloading audio from YouTube...")
        raw_audio_path, video_metadata = downloader.download_audio(youtube_url, job_id)
        logger.info(f"Downloaded: {raw_audio_path} ({video_metadata.get('file_size_mb', 0):.2f} MB)")
        
        # Step 4: Process audio
        logger.info("Processing audio for optimal STT...")
        processed_audio_path, audio_metadata = audio_extractor.extract_from_file(raw_audio_path, job_id)
        logger.info(f"Processed: {processed_audio_path} ({audio_metadata.get('processed_file_size_mb', 0):.2f} MB)")
        
        # Step 5: Split into chunks
        logger.info("Splitting audio into chunks...")
        chunk_files = audio_extractor.split_audio_if_needed(
            processed_audio_path, 
            job_id, 
            max_chunk_size_mb=chunk_size_mb
        )
        
        # Step 6: Display results
        logger.info(f"Successfully created {len(chunk_files)} chunks:")
        
        total_size_mb = 0
        for i, chunk_file in enumerate(chunk_files):
            chunk_path = Path(chunk_file)
            chunk_size_mb = chunk_path.stat().st_size / (1024 * 1024)
            total_size_mb += chunk_size_mb
            logger.info(f"  Chunk {i+1}: {chunk_file} ({chunk_size_mb:.2f} MB)")
        
        logger.info(f"Total size: {total_size_mb:.2f} MB")
        logger.info(f"Original duration: {audio_metadata.get('duration_seconds', 0):.1f} seconds")
        
        # Restore original settings if modified
        if output_dir:
            settings.local_storage_path = original_path
        
        return chunk_files
        
    except Exception as e:
        logger.error(f"Extraction failed: {str(e)}")
        # Restore original settings if modified
        if output_dir:
            settings.local_storage_path = original_path
        raise


def main():
    """Main function"""
    
    parser = argparse.ArgumentParser(
        description="Extract chunked WAV files from YouTube video",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract chunks from YouTube video
  python scripts/extract_chunked_audio.py --url https://youtu.be/QBiaM7BXsY4
  
  # Extract with custom job ID and chunk size
  python scripts/extract_chunked_audio.py --url https://youtu.be/QBiaM7BXsY4 --job-id sermon-2024 --chunk-size 5.0
  
  # Extract to specific output directory
  python scripts/extract_chunked_audio.py --url https://youtu.be/QBiaM7BXsY4 --output-dir ./output
        """
    )
    
    parser.add_argument(
        "--url",
        required=True,
        help="YouTube video URL"
    )
    
    parser.add_argument(
        "--job-id",
        help="Job identifier (will generate UUID if not provided)"
    )
    
    parser.add_argument(
        "--chunk-size",
        type=float,
        default=9.0,
        help="Maximum chunk size in MB (default: 9.0)"
    )
    
    parser.add_argument(
        "--output-dir",
        help="Output directory for chunk files (default: uses app settings)"
    )
    
    parser.add_argument(
        "--info-only",
        action="store_true",
        help="Only get video info, don't download"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        if args.info_only:
            # Only get video information
            downloader = YouTubeDownloader()
            video_info = downloader.get_video_info(args.url)
            
            print(f"Title: {video_info.get('title', 'N/A')}")
            print(f"Author: {video_info.get('author', 'N/A')}")
            print(f"Duration: {video_info.get('length', 0)} seconds ({video_info.get('length', 0)/60:.1f} minutes)")
            print(f"Views: {video_info.get('views', 0):,}")
            print(f"Upload Date: {video_info.get('publish_date', 'N/A')}")
            
        else:
            # Extract chunked audio
            chunk_files = extract_chunked_audio(
                youtube_url=args.url,
                job_id=args.job_id,
                chunk_size_mb=args.chunk_size,
                output_dir=args.output_dir
            )
            
            print(f"\nSuccessfully extracted {len(chunk_files)} chunks:")
            for chunk_file in chunk_files:
                print(f"  {chunk_file}")
    
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()