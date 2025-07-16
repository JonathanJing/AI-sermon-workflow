#!/usr/bin/env python3
"""
Quick test script for YouTube extraction: https://youtu.be/wl7zlu4YoA4
"""

import sys
import logging
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ingest.downloader import YouTubeDownloader
from app.services.ingest.audio_extractor import AudioExtractor
from pydub import AudioSegment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def quick_youtube_test():
    """Quick test of YouTube extraction workflow"""
    
    # Test URL
    test_url = "https://youtu.be/wl7zlu4YoA4"
    job_id = "quick_youtube_test"
    
    try:
        # 1. Download from YouTube
        logger.info("Step 1: Downloading from YouTube...")
        logger.info(f"URL: {test_url}")
        
        downloader = YouTubeDownloader()
        audio_path = downloader.download_audio(test_url, job_id)
        
        if not audio_path:
            logger.error("❌ Failed to download audio")
            return False
        
        # Get file info
        audio_file = Path(audio_path)
        file_size_mb = audio_file.stat().st_size / (1024 * 1024)
        
        # Get audio properties
        audio = AudioSegment.from_file(audio_path)
        duration_s = len(audio) / 1000.0
        duration_min = duration_s / 60.0
        
        logger.info(f"✅ Download successful:")
        logger.info(f"  - File: {audio_path}")
        logger.info(f"  - Size: {file_size_mb:.2f} MB")
        logger.info(f"  - Duration: {duration_s:.1f}s ({duration_min:.1f} minutes)")
        logger.info(f"  - Sample rate: {audio.frame_rate} Hz")
        logger.info(f"  - Channels: {audio.channels}")
        logger.info(f"  - Bit depth: {audio.sample_width * 8}-bit")
        
        # 2. Test chunking
        logger.info("Step 2: Testing chunking...")
        
        extractor = AudioExtractor()
        chunk_files = extractor.split_audio_if_needed(audio_path, job_id, max_chunk_size_mb=8.0)
        
        logger.info(f"✅ Chunking successful:")
        logger.info(f"  - Created {len(chunk_files)} chunks")
        
        # Validate chunks
        google_limit_mb = 10.0
        valid_chunks = 0
        total_chunk_duration = 0.0
        
        for i, chunk_file in enumerate(chunk_files):
            chunk_path = Path(chunk_file)
            chunk_size_mb = chunk_path.stat().st_size / (1024 * 1024)
            
            chunk_audio = AudioSegment.from_wav(chunk_file)
            chunk_duration_s = len(chunk_audio) / 1000.0
            total_chunk_duration += chunk_duration_s
            
            is_valid = (
                chunk_size_mb <= google_limit_mb and
                chunk_duration_s >= 5.0 and
                chunk_duration_s <= 60.0 and
                chunk_audio.frame_rate >= 16000
            )
            
            if is_valid:
                valid_chunks += 1
            
            status = "✅" if is_valid else "❌"
            logger.info(f"  Chunk {i+1}: {chunk_size_mb:.2f}MB, {chunk_duration_s:.1f}s, {chunk_audio.frame_rate}Hz {status}")
        
        # Check duration preservation
        duration_preservation = abs(total_chunk_duration - duration_s) / duration_s * 100
        
        logger.info(f"  - Valid chunks: {valid_chunks}/{len(chunk_files)}")
        logger.info(f"  - Duration preservation: {duration_preservation:.1f}%")
        
        # 3. Cleanup
        logger.info("Step 3: Cleaning up...")
        
        # Clean up chunks
        for chunk_file in chunk_files:
            if Path(chunk_file).exists():
                Path(chunk_file).unlink()
        
        # Clean up original
        if Path(audio_path).exists():
            Path(audio_path).unlink()
        
        logger.info("✅ Cleanup completed")
        
        # 4. Summary
        success = valid_chunks == len(chunk_files) and duration_preservation < 5.0
        
        if success:
            logger.info("🎉 Quick YouTube test PASSED!")
            logger.info("The video is ready for STT processing")
        else:
            logger.error("❌ Quick YouTube test FAILED!")
            logger.error("Some chunks are invalid or duration not preserved")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Quick YouTube test FAILED: {str(e)}")
        return False


if __name__ == "__main__":
    success = quick_youtube_test()
    sys.exit(0 if success else 1)