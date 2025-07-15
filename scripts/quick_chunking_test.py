#!/usr/bin/env python3
"""
Quick test script to verify chunking system with YouTube audio
"""

import sys
import logging
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ingest.downloader import YouTubeDownloader
from app.services.ingest.audio_extractor import AudioExtractor
from app.services.stt.google_stt import GoogleSTTService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def quick_test():
    """Quick test with the YouTube video from the conversation"""
    
    # Test URL from the conversation
    test_url = "https://youtu.be/QBiaM7BXsY4"
    job_id = "quick_test"
    
    try:
        # Download
        logger.info("Downloading YouTube audio...")
        downloader = YouTubeDownloader()
        audio_path = downloader.download_audio(test_url, job_id)
        
        if not audio_path:
            logger.error("Failed to download audio")
            return False
            
        original_size_mb = Path(audio_path).stat().st_size / (1024 * 1024)
        logger.info(f"Downloaded audio: {original_size_mb:.2f}MB")
        
        # Extract and chunk
        logger.info("Processing audio and creating chunks...")
        extractor = AudioExtractor()
        chunk_files = extractor.split_audio_if_needed(audio_path, job_id, max_chunk_size_mb=8.0)
        
        logger.info(f"Created {len(chunk_files)} chunks")
        
        # Validate chunk sizes
        google_limit_mb = 10.0
        all_valid = True
        
        for i, chunk_file in enumerate(chunk_files):
            chunk_path = Path(chunk_file)
            chunk_size_mb = chunk_path.stat().st_size / (1024 * 1024)
            
            status = "✅" if chunk_size_mb <= google_limit_mb else "❌"
            logger.info(f"Chunk {i+1}: {chunk_size_mb:.2f}MB {status}")
            
            if chunk_size_mb > google_limit_mb:
                all_valid = False
                logger.error(f"Chunk {i+1} exceeds 10MB limit!")
        
        # Test STT service chunk detection
        logger.info("Testing STT service chunk detection...")
        stt_service = GoogleSTTService()
        audio_path_obj = Path(audio_path)
        detected_chunks = stt_service._find_chunk_files(audio_path_obj, job_id)
        
        logger.info(f"STT detected {len(detected_chunks)} chunks")
        
        # Validate chunk detection
        if len(detected_chunks) == len(chunk_files):
            logger.info("✅ Chunk detection successful")
        else:
            logger.error(f"❌ Chunk detection failed: expected {len(chunk_files)}, got {len(detected_chunks)}")
            all_valid = False
        
        # Cleanup
        logger.info("Cleaning up files...")
        for chunk_file in chunk_files:
            if Path(chunk_file).exists():
                Path(chunk_file).unlink()
        
        if Path(audio_path).exists():
            Path(audio_path).unlink()
        
        if all_valid:
            logger.info("🎉 Quick test PASSED - all chunks under 10MB limit")
            return True
        else:
            logger.error("❌ Quick test FAILED - chunks exceed 10MB limit")
            return False
            
    except Exception as e:
        logger.error(f"Quick test failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = quick_test()
    sys.exit(0 if success else 1)