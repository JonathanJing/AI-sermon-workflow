#!/usr/bin/env python3
"""
Test script to verify 16kHz minimum sample rate enforcement
"""

import sys
import logging
from pathlib import Path
import tempfile

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ingest.audio_extractor import AudioExtractor
from pydub import AudioSegment
from pydub.generators import Sine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_audio_with_sample_rate(duration_s: int, sample_rate: int, channels: int = 2) -> AudioSegment:
    """Create test audio with specific sample rate"""
    # Create a sine wave
    tone = Sine(440).to_audio_segment(duration=duration_s * 1000)
    
    # Set desired properties
    tone = tone.set_frame_rate(sample_rate)
    tone = tone.set_channels(channels)
    tone = tone.set_sample_width(4)  # 32-bit
    
    return tone


def test_sample_rate_enforcement():
    """Test that sample rate is never reduced below 16kHz"""
    logger.info("=== Testing Sample Rate Enforcement ===")
    
    extractor = AudioExtractor()
    
    # Test scenarios with different original sample rates
    test_scenarios = [
        {"original_rate": 48000, "duration": 600, "expected_min": 16000},  # 10 minutes at 48kHz
        {"original_rate": 44100, "duration": 600, "expected_min": 16000},  # 10 minutes at 44.1kHz
        {"original_rate": 32000, "duration": 600, "expected_min": 16000},  # 10 minutes at 32kHz
        {"original_rate": 22050, "duration": 600, "expected_min": 16000},  # 10 minutes at 22.05kHz
        {"original_rate": 16000, "duration": 600, "expected_min": 16000},  # 10 minutes at 16kHz (should stay)
        {"original_rate": 8000, "duration": 600, "expected_min": 16000},   # 10 minutes at 8kHz (should be upsampled)
    ]
    
    for scenario in test_scenarios:
        logger.info(f"\nTesting: {scenario['original_rate']}Hz → should be ≥ {scenario['expected_min']}Hz")
        
        # Create test audio
        test_audio = create_test_audio_with_sample_rate(
            scenario['duration'], 
            scenario['original_rate']
        )
        
        original_size_mb = extractor._estimate_wav_size(test_audio)
        logger.info(f"Original: {scenario['original_rate']}Hz, {original_size_mb:.2f}MB")
        
        # Process audio (this will trigger compression if needed)
        processed_audio = extractor._process_for_stt(test_audio, f"test_{scenario['original_rate']}", target_size_mb=8.0)
        
        # Check final sample rate
        final_rate = processed_audio.frame_rate
        final_size_mb = extractor._estimate_wav_size(processed_audio)
        
        logger.info(f"Final: {final_rate}Hz, {final_size_mb:.2f}MB")
        
        # Validate sample rate is not below 16kHz
        assert final_rate >= scenario['expected_min'], f"Sample rate {final_rate}Hz is below minimum {scenario['expected_min']}Hz"
        
        # Validate audio quality preservation
        assert final_rate >= 16000, f"Audio quality compromised: {final_rate}Hz < 16kHz"
        
        logger.info(f"✅ Sample rate properly enforced: {final_rate}Hz ≥ 16kHz")
    
    logger.info("\n✅ All sample rate enforcement tests passed!")


def test_compression_alternatives():
    """Test that alternative compression methods are used instead of reducing sample rate below 16kHz"""
    logger.info("\n=== Testing Compression Alternatives ===")
    
    extractor = AudioExtractor()
    
    # Create a large audio file that will need aggressive compression
    large_audio = create_test_audio_with_sample_rate(1800, 16000, 2)  # 30 minutes at 16kHz
    original_size_mb = extractor._estimate_wav_size(large_audio)
    
    logger.info(f"Large test audio: {large_audio.frame_rate}Hz, {original_size_mb:.2f}MB")
    
    # Process with aggressive compression target
    processed_audio = extractor._process_for_stt(large_audio, "compression_test", target_size_mb=2.0)
    
    final_rate = processed_audio.frame_rate
    final_size_mb = extractor._estimate_wav_size(processed_audio)
    
    logger.info(f"After compression: {final_rate}Hz, {final_size_mb:.2f}MB")
    
    # Validate sample rate maintained
    assert final_rate >= 16000, f"Sample rate reduced below 16kHz: {final_rate}Hz"
    
    # Validate size reduction achieved
    compression_ratio = final_size_mb / original_size_mb
    logger.info(f"Compression ratio: {compression_ratio:.2f}")
    
    # Should achieve significant compression without reducing sample rate below 16kHz
    assert compression_ratio < 0.5, f"Compression not aggressive enough: {compression_ratio:.2f}"
    
    logger.info("✅ Compression alternatives working correctly!")


def test_chunking_with_16khz_minimum():
    """Test that chunking maintains 16kHz minimum"""
    logger.info("\n=== Testing Chunking with 16kHz Minimum ===")
    
    extractor = AudioExtractor()
    
    # Create large audio that will be chunked
    large_audio = create_test_audio_with_sample_rate(2700, 48000, 2)  # 45 minutes at 48kHz
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save large audio
        large_audio_path = Path(temp_dir) / "large_test.wav"
        large_audio.export(str(large_audio_path), format="wav")
        
        logger.info(f"Large audio file: {large_audio_path}, size: {large_audio_path.stat().st_size / (1024*1024):.2f}MB")
        
        # Test chunking
        job_id = "chunking_sample_rate_test"
        chunk_files = extractor.split_audio_if_needed(str(large_audio_path), job_id, max_chunk_size_mb=8.0)
        
        logger.info(f"Created {len(chunk_files)} chunks")
        
        # Validate each chunk's sample rate
        for i, chunk_file in enumerate(chunk_files):
            chunk_audio = AudioSegment.from_wav(chunk_file)
            chunk_rate = chunk_audio.frame_rate
            chunk_size_mb = Path(chunk_file).stat().st_size / (1024 * 1024)
            
            logger.info(f"Chunk {i+1}: {chunk_rate}Hz, {chunk_size_mb:.2f}MB")
            
            assert chunk_rate >= 16000, f"Chunk {i+1} sample rate below 16kHz: {chunk_rate}Hz"
            assert chunk_size_mb <= 10.0, f"Chunk {i+1} exceeds 10MB limit: {chunk_size_mb:.2f}MB"
        
        # Cleanup
        for chunk_file in chunk_files:
            if Path(chunk_file).exists():
                Path(chunk_file).unlink()
    
    logger.info("✅ Chunking maintains 16kHz minimum!")


def run_all_tests():
    """Run all sample rate validation tests"""
    logger.info("Starting 16kHz Minimum Sample Rate Validation Tests")
    logger.info("=" * 60)
    
    try:
        test_sample_rate_enforcement()
        test_compression_alternatives()
        test_chunking_with_16khz_minimum()
        
        logger.info("=" * 60)
        logger.info("🎉 ALL TESTS PASSED! 16kHz minimum sample rate properly enforced")
        
    except Exception as e:
        logger.error(f"❌ TEST FAILED: {str(e)}")
        raise


if __name__ == "__main__":
    run_all_tests()