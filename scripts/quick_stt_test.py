#!/usr/bin/env python3
"""
Quick STT test script - minimal test for single chunk conversion
"""

import sys
import logging
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ingest.downloader import YouTubeDownloader
from app.services.ingest.audio_extractor import AudioExtractor
from app.services.stt.google_stt import GoogleSTTService
from pydub import AudioSegment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def quick_stt_test():
    """Quick test of single chunk STT conversion"""
    
    # Test URL from conversation
    test_url = "https://youtu.be/QBiaM7BXsY4"
    job_id = "quick_stt_test"
    
    try:
        # 1. Download and create chunk
        logger.info("Step 1: Downloading and creating test chunk...")
        downloader = YouTubeDownloader()
        audio_path = downloader.download_audio(test_url, f"{job_id}_source")
        
        if not audio_path:
            logger.error("❌ Failed to download audio")
            return False
        
        # Extract first 30 seconds
        audio = AudioSegment.from_file(audio_path)
        chunk = audio[:30000]  # 30 seconds
        
        # Process for STT
        extractor = AudioExtractor()
        processed_chunk = extractor._process_for_stt(chunk, job_id, target_size_mb=8.0)
        
        # Save chunk
        chunk_path = Path(extractor.output_path) / f"{job_id}_chunk.wav"
        processed_chunk.export(str(chunk_path), format="wav")
        
        # Validate chunk
        chunk_size_mb = chunk_path.stat().st_size / (1024 * 1024)
        chunk_duration_s = len(processed_chunk) / 1000
        
        logger.info(f"✅ Chunk created: {chunk_size_mb:.2f}MB, {chunk_duration_s:.1f}s, {processed_chunk.frame_rate}Hz")
        
        # Check Google STT compatibility
        if chunk_size_mb > 10.0:
            logger.error(f"❌ Chunk too large for Google STT: {chunk_size_mb:.2f}MB > 10MB")
            return False
        
        if processed_chunk.frame_rate < 16000:
            logger.error(f"❌ Sample rate too low: {processed_chunk.frame_rate}Hz < 16kHz")
            return False
        
        # 2. Test STT conversion
        logger.info("Step 2: Testing STT conversion...")
        stt_service = GoogleSTTService()
        
        if not stt_service.client:
            logger.error("❌ Google STT client not available (check credentials)")
            return False
        
        # Perform transcription
        transcript_result, metadata = stt_service._transcribe_single_file(str(chunk_path), job_id)
        
        # Display results
        logger.info(f"✅ STT conversion successful:")
        logger.info(f"  - Entries: {len(transcript_result.entries)}")
        logger.info(f"  - Duration: {transcript_result.total_duration:.1f}s")
        logger.info(f"  - Confidence: {transcript_result.confidence:.3f if transcript_result.confidence else 'N/A'}")
        logger.info(f"  - Language: {transcript_result.language}")
        logger.info(f"  - Method: {metadata.get('transcription_method', 'unknown')}")
        logger.info(f"  - Cost: ${metadata.get('estimated_cost_usd', 0):.4f}")
        
        # Show transcript
        logger.info("Transcript:")
        for i, entry in enumerate(transcript_result.entries):
            logger.info(f"  {i+1}. [{entry.start_time:.1f}s-{entry.end_time:.1f}s] {entry.text}")
        
        # 3. Cleanup
        logger.info("Step 3: Cleaning up...")
        if chunk_path.exists():
            chunk_path.unlink()
        if Path(audio_path).exists():
            Path(audio_path).unlink()
        
        logger.info("🎉 Quick STT test PASSED!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Quick STT test FAILED: {str(e)}")
        return False


if __name__ == "__main__":
    success = quick_stt_test()
    sys.exit(0 if success else 1)