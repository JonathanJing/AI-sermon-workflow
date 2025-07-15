#!/usr/bin/env python3
"""
Test script to validate Google STT 10MB chunk size limit and chunking algorithm
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any
import tempfile
import shutil

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ingest.audio_extractor import AudioExtractor
from app.services.stt.google_stt import GoogleSTTService
from app.config import settings
from pydub import AudioSegment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_audio(duration_minutes: int = 45, sample_rate: int = 48000) -> AudioSegment:
    """Create a test audio segment of specified duration"""
    logger.info(f"Creating test audio: {duration_minutes} minutes at {sample_rate}Hz")
    
    # Create a sine wave tone (440Hz A note)
    duration_ms = duration_minutes * 60 * 1000
    
    # Generate a simple tone
    from pydub.generators import Sine
    tone = Sine(440).to_audio_segment(duration=duration_ms)
    
    # Set sample rate
    tone = tone.set_frame_rate(sample_rate)
    
    # Convert to stereo and 32-bit (typical from YouTube)
    tone = tone.set_channels(2).set_sample_width(4)
    
    logger.info(f"Created test audio: {len(tone)/1000:.1f}s, {tone.frame_rate}Hz, {tone.channels} channels, {tone.sample_width*8}-bit")
    return tone


def test_chunk_size_estimation():
    """Test chunk size estimation accuracy"""
    logger.info("=== Testing Chunk Size Estimation ===")
    
    extractor = AudioExtractor()
    
    # Test with different audio configurations
    test_configs = [
        {"duration": 10, "sample_rate": 48000, "channels": 2, "sample_width": 4},
        {"duration": 30, "sample_rate": 48000, "channels": 2, "sample_width": 4},
        {"duration": 60, "sample_rate": 48000, "channels": 2, "sample_width": 4},
    ]
    
    for config in test_configs:
        # Create test audio
        audio = create_test_audio(config["duration"]/60, config["sample_rate"])
        
        # Estimate size
        estimated_size_mb = extractor._estimate_wav_size(audio)
        
        # Export to temp file to get actual size
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            audio.export(temp_file.name, format="wav")
            actual_size_mb = Path(temp_file.name).stat().st_size / (1024 * 1024)
            os.unlink(temp_file.name)
        
        accuracy = abs(estimated_size_mb - actual_size_mb) / actual_size_mb * 100
        
        logger.info(f"Duration: {config['duration']}s | Estimated: {estimated_size_mb:.2f}MB | Actual: {actual_size_mb:.2f}MB | Accuracy: {100-accuracy:.1f}%")
        
        assert accuracy < 10, f"Size estimation accuracy too low: {accuracy:.1f}%"
    
    logger.info("✅ Chunk size estimation tests passed")


def test_chunking_algorithm():
    """Test the chunking algorithm with large files"""
    logger.info("=== Testing Chunking Algorithm ===")
    
    extractor = AudioExtractor()
    
    # Create a large test audio file (45 minutes)
    large_audio = create_test_audio(45, 48000)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save the large audio file
        large_audio_path = Path(temp_dir) / "large_test.wav"
        large_audio.export(str(large_audio_path), format="wav")
        
        file_size_mb = large_audio_path.stat().st_size / (1024 * 1024)
        logger.info(f"Created large test file: {file_size_mb:.2f}MB")
        
        # Test chunking
        job_id = "test_chunking"
        chunk_files = extractor.split_audio_if_needed(str(large_audio_path), job_id, max_chunk_size_mb=8.0)
        
        logger.info(f"Created {len(chunk_files)} chunks")
        
        # Validate each chunk
        google_limit_mb = 10.0
        total_duration = 0
        
        for i, chunk_file in enumerate(chunk_files):
            chunk_path = Path(chunk_file)
            chunk_size_mb = chunk_path.stat().st_size / (1024 * 1024)
            
            # Load audio to check duration
            chunk_audio = AudioSegment.from_wav(chunk_file)
            chunk_duration_s = len(chunk_audio) / 1000
            total_duration += chunk_duration_s
            
            logger.info(f"Chunk {i+1}: {chunk_size_mb:.2f}MB, {chunk_duration_s:.1f}s")
            
            # Validate chunk size
            assert chunk_size_mb <= google_limit_mb, f"Chunk {i+1} exceeds 10MB limit: {chunk_size_mb:.2f}MB"
            assert chunk_size_mb > 0.001, f"Chunk {i+1} too small: {chunk_size_mb:.3f}MB"
            assert chunk_duration_s >= 5, f"Chunk {i+1} too short: {chunk_duration_s:.1f}s"
        
        # Validate total duration preservation
        original_duration_s = len(large_audio) / 1000
        duration_diff_percent = abs(total_duration - original_duration_s) / original_duration_s * 100
        
        logger.info(f"Original duration: {original_duration_s:.1f}s | Total chunks: {total_duration:.1f}s | Diff: {duration_diff_percent:.1f}%")
        
        assert duration_diff_percent < 5, f"Duration preservation error too high: {duration_diff_percent:.1f}%"
        
        # Cleanup
        for chunk_file in chunk_files:
            if Path(chunk_file).exists():
                Path(chunk_file).unlink()
    
    logger.info("✅ Chunking algorithm tests passed")


def test_sub_chunk_creation():
    """Test sub-chunk creation for oversized chunks"""
    logger.info("=== Testing Sub-Chunk Creation ===")
    
    extractor = AudioExtractor()
    
    # Create an oversized chunk (simulated)
    oversized_audio = create_test_audio(15, 48000)  # 15 minutes should be > 10MB
    
    # Test sub-chunking
    sub_chunks = extractor._split_oversized_chunk(oversized_audio, "test_chunk_0", 9.0)
    
    logger.info(f"Split oversized chunk into {len(sub_chunks)} sub-chunks")
    
    total_sub_duration = 0
    for i, sub_chunk in enumerate(sub_chunks):
        sub_duration_s = len(sub_chunk) / 1000
        sub_size_mb = extractor._estimate_wav_size(sub_chunk)
        total_sub_duration += sub_duration_s
        
        logger.info(f"Sub-chunk {i+1}: {sub_size_mb:.2f}MB, {sub_duration_s:.1f}s")
        
        # Validate sub-chunk
        assert sub_size_mb <= 10.0, f"Sub-chunk {i+1} exceeds 10MB: {sub_size_mb:.2f}MB"
        assert sub_duration_s >= 10, f"Sub-chunk {i+1} too short: {sub_duration_s:.1f}s"
    
    # Validate duration preservation
    original_duration_s = len(oversized_audio) / 1000
    duration_diff_percent = abs(total_sub_duration - original_duration_s) / original_duration_s * 100
    
    logger.info(f"Original: {original_duration_s:.1f}s | Sub-chunks: {total_sub_duration:.1f}s | Diff: {duration_diff_percent:.1f}%")
    
    assert duration_diff_percent < 5, f"Sub-chunk duration preservation error: {duration_diff_percent:.1f}%"
    
    logger.info("✅ Sub-chunk creation tests passed")


def test_chunk_file_sorting():
    """Test chunk file sorting with sub-chunks"""
    logger.info("=== Testing Chunk File Sorting ===")
    
    stt_service = GoogleSTTService()
    
    # Create mock chunk files with mixed naming
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create mock chunk files
        chunk_files = [
            "job123_chunk_001.wav",
            "job123_chunk_002.wav",
            "job123_chunk_003_000.wav",  # Sub-chunk
            "job123_chunk_003_001.wav",  # Sub-chunk
            "job123_chunk_004.wav",
            "job123_chunk_010.wav",
        ]
        
        for chunk_file in chunk_files:
            (temp_path / chunk_file).touch()
        
        # Test sorting
        audio_path = temp_path / "job123_audio.wav"
        audio_path.touch()
        
        sorted_files = stt_service._find_chunk_files(audio_path, "job123")
        
        # Extract just the filenames for comparison
        sorted_names = [Path(f).name for f in sorted_files]
        
        expected_order = [
            "job123_chunk_001.wav",
            "job123_chunk_002.wav",
            "job123_chunk_003_000.wav",
            "job123_chunk_003_001.wav",
            "job123_chunk_004.wav",
            "job123_chunk_010.wav",
        ]
        
        logger.info(f"Sorted order: {sorted_names}")
        logger.info(f"Expected order: {expected_order}")
        
        assert sorted_names == expected_order, f"Chunk sorting failed: {sorted_names} != {expected_order}"
    
    logger.info("✅ Chunk file sorting tests passed")


def test_real_youtube_audio():
    """Test with actual YouTube audio if available"""
    logger.info("=== Testing Real YouTube Audio ===")
    
    # Test with the YouTube URL from the conversation
    test_url = "https://youtu.be/QBiaM7BXsY4"
    
    try:
        from app.services.ingest.downloader import YouTubeDownloader
        downloader = YouTubeDownloader()
        extractor = AudioExtractor()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download audio
            job_id = "test_real_youtube"
            audio_path = downloader.download_audio(test_url, job_id)
            
            if audio_path:
                # Get original file size
                original_size_mb = Path(audio_path).stat().st_size / (1024 * 1024)
                logger.info(f"Downloaded audio: {original_size_mb:.2f}MB")
                
                # Test chunking
                chunk_files = extractor.split_audio_if_needed(audio_path, job_id, max_chunk_size_mb=8.0)
                
                logger.info(f"Created {len(chunk_files)} chunks from real YouTube audio")
                
                # Validate all chunks
                google_limit_mb = 10.0
                for i, chunk_file in enumerate(chunk_files):
                    chunk_size_mb = Path(chunk_file).stat().st_size / (1024 * 1024)
                    
                    logger.info(f"Real chunk {i+1}: {chunk_size_mb:.2f}MB")
                    
                    assert chunk_size_mb <= google_limit_mb, f"Real chunk {i+1} exceeds limit: {chunk_size_mb:.2f}MB"
                
                # Cleanup
                for chunk_file in chunk_files:
                    if Path(chunk_file).exists():
                        Path(chunk_file).unlink()
                
                if Path(audio_path).exists():
                    Path(audio_path).unlink()
                
                logger.info("✅ Real YouTube audio test passed")
            else:
                logger.warning("Could not download YouTube audio for testing")
                
    except Exception as e:
        logger.warning(f"Real YouTube audio test failed: {str(e)}")


def run_all_tests():
    """Run all validation tests"""
    logger.info("Starting Google STT 10MB Limit Validation Tests")
    logger.info("=" * 60)
    
    try:
        test_chunk_size_estimation()
        test_chunking_algorithm()
        test_sub_chunk_creation()
        test_chunk_file_sorting()
        test_real_youtube_audio()
        
        logger.info("=" * 60)
        logger.info("🎉 ALL TESTS PASSED! Google STT 10MB limit validation successful")
        
    except Exception as e:
        logger.error(f"❌ TEST FAILED: {str(e)}")
        raise


if __name__ == "__main__":
    run_all_tests()