#!/usr/bin/env python3
"""
Test script to verify GCS upload support for long audio chunks
"""

import sys
import logging
from pathlib import Path
import tempfile
import argparse

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ingest.audio_extractor import AudioExtractor
from app.services.stt.google_stt import GoogleSTTService
from app.config import settings
from pydub import AudioSegment
from pydub.generators import Sine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_long_test_audio(duration_s: int = 90, sample_rate: int = 16000) -> AudioSegment:
    """Create a long test audio file (>60s) to test GCS upload"""
    logger.info(f"Creating long test audio: {duration_s}s at {sample_rate}Hz")
    
    # Create a sine wave tone
    tone = Sine(440).to_audio_segment(duration=duration_s * 1000)
    
    # Set proper audio properties
    tone = tone.set_frame_rate(sample_rate)
    tone = tone.set_channels(1)
    tone = tone.set_sample_width(2)  # 16-bit
    
    logger.info(f"Created long test audio: {len(tone)/1000:.1f}s, {tone.frame_rate}Hz, {tone.channels} channels, {tone.sample_width*8}-bit")
    return tone


def test_gcs_configuration():
    """Test GCS configuration"""
    logger.info("=== Testing GCS Configuration ===")
    
    # Check if GCS library is available
    try:
        from google.cloud import storage
        gcs_available = True
        logger.info("✅ Google Cloud Storage library is available")
    except ImportError:
        gcs_available = False
        logger.error("❌ Google Cloud Storage library not available")
        logger.error("Install with: pip install google-cloud-storage")
        return False
    
    # Check configuration
    config_issues = []
    
    if not settings.google_cloud.credentials_path:
        config_issues.append("GOOGLE_APPLICATION_CREDENTIALS not set")
    
    if not settings.google_cloud.project_id:
        config_issues.append("Google Cloud project ID not set")
    
    if not settings.google_cloud.bucket_name:
        config_issues.append("GCS bucket name not set")
    
    if config_issues:
        logger.error("❌ GCS configuration issues:")
        for issue in config_issues:
            logger.error(f"  - {issue}")
        logger.error("Please configure GCS settings in .env file:")
        logger.error("  GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json")
        logger.error("  GOOGLE_CLOUD_PROJECT=your-project-id")
        logger.error("  GCS_BUCKET_NAME=your-bucket-name")
        return False
    
    logger.info("✅ GCS configuration looks good:")
    logger.info(f"  - Project: {settings.google_cloud.project_id}")
    logger.info(f"  - Bucket: {settings.google_cloud.bucket_name}")
    logger.info(f"  - Credentials: {settings.google_cloud.credentials_path}")
    
    return True


def test_gcs_upload_functionality():
    """Test GCS upload functionality with long audio"""
    logger.info("=== Testing GCS Upload Functionality ===")
    
    try:
        # Create long test audio (90 seconds - exceeds 60s limit)
        long_audio = create_long_test_audio(90, 16000)
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            long_audio.export(temp_file.name, format="wav")
            temp_path = temp_file.name
        
        logger.info(f"Created long test audio file: {temp_path}")
        
        # Test STT service with long audio
        stt_service = GoogleSTTService()
        
        if not stt_service.client:
            logger.error("❌ Google STT client not initialized")
            return False
        
        if not stt_service.storage_client:
            logger.error("❌ Google Storage client not initialized")
            return False
        
        # Test transcription (this should trigger GCS upload)
        job_id = "gcs_test_long_audio"
        logger.info(f"Starting transcription of 90s audio file (should use GCS)")
        
        transcript_result, metadata = stt_service._transcribe_single_file(temp_path, job_id)
        
        # Check results
        logger.info(f"✅ Long audio transcription successful:")
        logger.info(f"  - Entries: {len(transcript_result.entries)}")
        logger.info(f"  - Duration: {transcript_result.total_duration:.1f}s")
        logger.info(f"  - Method: {metadata.get('transcription_method', 'unknown')}")
        logger.info(f"  - Cost: ${metadata.get('estimated_cost_usd', 0):.4f}")
        
        # Cleanup
        Path(temp_path).unlink()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ GCS upload test failed: {str(e)}")
        return False


def test_chunked_audio_duration_limits():
    """Test that chunked audio respects duration limits"""
    logger.info("=== Testing Chunked Audio Duration Limits ===")
    
    try:
        # Create very long audio (10 minutes)
        very_long_audio = create_long_test_audio(600, 16000)  # 10 minutes
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            very_long_audio.export(temp_file.name, format="wav")
            temp_path = temp_file.name
        
        logger.info(f"Created very long test audio file: {temp_path}")
        
        # Test chunking
        extractor = AudioExtractor()
        job_id = "chunked_duration_test"
        
        chunk_files = extractor.split_audio_if_needed(temp_path, job_id, max_chunk_size_mb=8.0)
        
        logger.info(f"Created {len(chunk_files)} chunks")
        
        # Validate each chunk duration
        duration_issues = []
        
        for i, chunk_file in enumerate(chunk_files):
            chunk_audio = AudioSegment.from_wav(chunk_file)
            chunk_duration_s = len(chunk_audio) / 1000.0
            
            logger.info(f"Chunk {i+1}: {chunk_duration_s:.1f}s")
            
            if chunk_duration_s > 60:
                duration_issues.append(f"Chunk {i+1} exceeds 60s limit: {chunk_duration_s:.1f}s")
        
        if duration_issues:
            logger.error("❌ Chunk duration issues:")
            for issue in duration_issues:
                logger.error(f"  - {issue}")
            return False
        
        logger.info("✅ All chunks respect 60s duration limit")
        
        # Cleanup
        Path(temp_path).unlink()
        for chunk_file in chunk_files:
            if Path(chunk_file).exists():
                Path(chunk_file).unlink()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Chunked duration test failed: {str(e)}")
        return False


def run_all_tests():
    """Run all GCS STT tests"""
    logger.info("Starting GCS STT Support Tests")
    logger.info("=" * 50)
    
    tests_passed = 0
    total_tests = 3
    
    # Test 1: GCS Configuration
    if test_gcs_configuration():
        tests_passed += 1
        logger.info("✅ Test 1/3 PASSED: GCS Configuration")
    else:
        logger.error("❌ Test 1/3 FAILED: GCS Configuration")
    
    print()
    
    # Test 2: GCS Upload Functionality
    if test_gcs_configuration():  # Only run if config is OK
        if test_gcs_upload_functionality():
            tests_passed += 1
            logger.info("✅ Test 2/3 PASSED: GCS Upload Functionality")
        else:
            logger.error("❌ Test 2/3 FAILED: GCS Upload Functionality")
    else:
        logger.error("❌ Test 2/3 SKIPPED: GCS Configuration issues")
    
    print()
    
    # Test 3: Chunked Audio Duration Limits
    if test_chunked_audio_duration_limits():
        tests_passed += 1
        logger.info("✅ Test 3/3 PASSED: Chunked Audio Duration Limits")
    else:
        logger.error("❌ Test 3/3 FAILED: Chunked Audio Duration Limits")
    
    print()
    
    # Summary
    logger.info("=" * 50)
    if tests_passed == total_tests:
        logger.info("🎉 ALL TESTS PASSED! GCS STT support is working correctly")
        return True
    else:
        logger.error(f"❌ {total_tests - tests_passed}/{total_tests} TESTS FAILED")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test GCS STT support")
    parser.add_argument("--config-only", action="store_true", help="Only test configuration")
    
    args = parser.parse_args()
    
    if args.config_only:
        success = test_gcs_configuration()
    else:
        success = run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()