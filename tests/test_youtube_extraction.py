#!/usr/bin/env python3
"""
Test file for YouTube extraction: https://youtu.be/wl7zlu4YoA4
Tests the complete workflow from YouTube download to STT processing
"""

import os
import sys
import logging
import json
from pathlib import Path
from typing import Dict, Any, List
import tempfile
import argparse
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ingest.downloader import YouTubeDownloader
from app.services.ingest.audio_extractor import AudioExtractor
from app.services.stt.google_stt import GoogleSTTService
from app.services.phrase_manager import PhraseManager
from app.config import settings
from pydub import AudioSegment

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class YouTubeExtractionTest:
    """Test class for YouTube extraction workflow"""
    
    def __init__(self, youtube_url: str, job_id: str = None):
        self.youtube_url = youtube_url
        self.job_id = job_id or f"yt_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.downloader = YouTubeDownloader()
        self.extractor = AudioExtractor()
        self.stt_service = None
        self.phrase_manager = PhraseManager()
        
        # Test results
        self.results = {
            "youtube_url": youtube_url,
            "job_id": self.job_id,
            "timestamp": datetime.now().isoformat(),
            "download_info": {},
            "audio_processing": {},
            "chunking_results": {},
            "stt_results": {},
            "files_created": [],
            "errors": [],
            "success": False
        }
    
    def test_youtube_download(self) -> bool:
        """Test YouTube download functionality"""
        logger.info("=== Testing YouTube Download ===")
        logger.info(f"URL: {self.youtube_url}")
        
        try:
            # Download audio
            audio_path, download_metadata = self.downloader.download_audio(self.youtube_url, self.job_id)
            
            if not audio_path:
                self.results["errors"].append("YouTube download failed - no audio path returned")
                return False
            
            # Check if file exists
            audio_file = Path(audio_path)
            if not audio_file.exists():
                self.results["errors"].append(f"Downloaded file not found: {audio_path}")
                return False
            
            # Get file info
            file_size_mb = audio_file.stat().st_size / (1024 * 1024)
            
            # Get audio properties
            try:
                audio_segment = AudioSegment.from_file(audio_path)
                duration_s = len(audio_segment) / 1000.0
                sample_rate = audio_segment.frame_rate
                channels = audio_segment.channels
                sample_width = audio_segment.sample_width
                
                self.results["download_info"] = {
                    "success": True,
                    "file_path": audio_path,
                    "file_size_mb": file_size_mb,
                    "duration_s": duration_s,
                    "sample_rate": sample_rate,
                    "channels": channels,
                    "sample_width": sample_width,
                    "bit_depth": sample_width * 8
                }
                
                logger.info(f"✅ Download successful:")
                logger.info(f"  - File: {audio_path}")
                logger.info(f"  - Size: {file_size_mb:.2f} MB")
                logger.info(f"  - Duration: {duration_s:.1f} seconds ({duration_s/60:.1f} minutes)")
                logger.info(f"  - Sample rate: {sample_rate} Hz")
                logger.info(f"  - Channels: {channels}")
                logger.info(f"  - Bit depth: {sample_width * 8}-bit")
                
                return True
                
            except Exception as e:
                self.results["errors"].append(f"Failed to analyze audio properties: {str(e)}")
                return False
                
        except Exception as e:
            self.results["errors"].append(f"YouTube download failed: {str(e)}")
            logger.error(f"❌ Download failed: {str(e)}")
            return False
    
    def test_audio_processing(self) -> bool:
        """Test audio processing for STT"""
        logger.info("=== Testing Audio Processing ===")
        
        try:
            # Check if download was successful
            if "file_path" not in self.results["download_info"]:
                raise ValueError("Download must be successful before audio processing")
            
            audio_path = self.results["download_info"]["file_path"]
            
            # Load original audio
            original_audio = AudioSegment.from_file(audio_path)
            
            # Process for STT
            processed_audio = self.extractor._process_for_stt(original_audio, self.job_id, target_size_mb=8.0)
            
            # Save processed audio
            processed_path = Path(self.extractor.output_path) / f"{self.job_id}_processed.wav"
            processed_audio.export(str(processed_path), format="wav")
            
            # Get processed audio info
            processed_size_mb = processed_path.stat().st_size / (1024 * 1024)
            processed_duration_s = len(processed_audio) / 1000.0
            
            # Check quality preservation
            original_duration_s = len(original_audio) / 1000.0
            duration_diff_percent = abs(processed_duration_s - original_duration_s) / original_duration_s * 100
            
            self.results["audio_processing"] = {
                "success": True,
                "processed_path": str(processed_path),
                "original_duration_s": original_duration_s,
                "processed_duration_s": processed_duration_s,
                "duration_preserved": duration_diff_percent < 5.0,
                "duration_diff_percent": duration_diff_percent,
                "original_size_mb": self.results["download_info"]["file_size_mb"],
                "processed_size_mb": processed_size_mb,
                "sample_rate": processed_audio.frame_rate,
                "channels": processed_audio.channels,
                "sample_width": processed_audio.sample_width,
                "google_stt_compatible": self._check_stt_compatibility(processed_audio, processed_size_mb)
            }
            
            logger.info(f"✅ Audio processing successful:")
            logger.info(f"  - Original: {original_duration_s:.1f}s, {self.results['download_info']['file_size_mb']:.2f}MB")
            logger.info(f"  - Processed: {processed_duration_s:.1f}s, {processed_size_mb:.2f}MB")
            logger.info(f"  - Duration difference: {duration_diff_percent:.1f}%")
            logger.info(f"  - Sample rate: {processed_audio.frame_rate}Hz")
            logger.info(f"  - Format: {processed_audio.sample_width * 8}-bit, {processed_audio.channels} channel(s)")
            
            self.results["files_created"].append(str(processed_path))
            return True
            
        except Exception as e:
            self.results["errors"].append(f"Audio processing failed: {str(e)}")
            logger.error(f"❌ Audio processing failed: {str(e)}")
            return False
    
    def test_chunking(self) -> bool:
        """Test audio chunking"""
        logger.info("=== Testing Audio Chunking ===")
        
        try:
            # Check if download was successful
            if "file_path" not in self.results["download_info"]:
                raise ValueError("Download must be successful before audio chunking")
            
            audio_path = self.results["download_info"]["file_path"]
            
            # Test chunking - use processed audio if available, otherwise original
            if "processed_path" in self.results["audio_processing"]:
                chunk_audio_path = self.results["audio_processing"]["processed_path"]
            else:
                chunk_audio_path = audio_path
            
            chunk_files = self.extractor.split_audio_if_needed(chunk_audio_path, self.job_id, max_chunk_size_mb=8.0)
            
            # Analyze chunks
            chunk_info = []
            total_chunk_duration = 0.0
            google_limit_mb = 10.0
            valid_chunks = 0
            
            for i, chunk_file in enumerate(chunk_files):
                chunk_path = Path(chunk_file)
                
                if chunk_path.exists():
                    chunk_size_mb = chunk_path.stat().st_size / (1024 * 1024)
                    
                    # Get audio properties
                    chunk_audio = AudioSegment.from_wav(chunk_file)
                    chunk_duration_s = len(chunk_audio) / 1000.0
                    total_chunk_duration += chunk_duration_s
                    
                    # Check validity
                    is_valid = (
                        chunk_size_mb <= google_limit_mb and
                        chunk_duration_s >= 5.0 and
                        chunk_duration_s <= 60.0 and
                        chunk_audio.frame_rate >= 16000
                    )
                    
                    if is_valid:
                        valid_chunks += 1
                    
                    chunk_info.append({
                        "chunk_number": i + 1,
                        "file_path": chunk_file,
                        "size_mb": chunk_size_mb,
                        "duration_s": chunk_duration_s,
                        "sample_rate": chunk_audio.frame_rate,
                        "valid": is_valid
                    })
                    
                    logger.info(f"  Chunk {i+1}: {chunk_size_mb:.2f}MB, {chunk_duration_s:.1f}s, {chunk_audio.frame_rate}Hz {'✅' if is_valid else '❌'}")
            
            # Calculate preservation
            original_duration_s = self.results["download_info"]["duration_s"]
            duration_preservation = abs(total_chunk_duration - original_duration_s) / original_duration_s * 100
            
            self.results["chunking_results"] = {
                "success": True,
                "total_chunks": len(chunk_files),
                "valid_chunks": valid_chunks,
                "chunk_info": chunk_info,
                "original_duration_s": original_duration_s,
                "total_chunk_duration_s": total_chunk_duration,
                "duration_preservation": duration_preservation < 5.0,
                "duration_preservation_percent": duration_preservation,
                "all_chunks_valid": valid_chunks == len(chunk_files)
            }
            
            logger.info(f"✅ Chunking successful:")
            logger.info(f"  - Total chunks: {len(chunk_files)}")
            logger.info(f"  - Valid chunks: {valid_chunks}/{len(chunk_files)}")
            logger.info(f"  - Duration preservation: {duration_preservation:.1f}%")
            
            self.results["files_created"].extend(chunk_files)
            return True
            
        except Exception as e:
            self.results["errors"].append(f"Chunking failed: {str(e)}")
            logger.error(f"❌ Chunking failed: {str(e)}")
            return False
    
    def test_stt_processing(self) -> bool:
        """Test STT processing"""
        logger.info("=== Testing STT Processing ===")
        
        try:
            # Initialize STT service
            self.stt_service = GoogleSTTService()
            
            if not self.stt_service.client:
                self.results["errors"].append("Google STT client not initialized - check credentials")
                logger.error("❌ Google STT client not initialized")
                return False
            
            # Test with processed audio
            # Check if download was successful
            if "file_path" not in self.results["download_info"]:
                raise ValueError("Download must be successful before STT processing")
            
            audio_path = self.results["download_info"]["file_path"]
            
            # Perform transcription
            transcript_result, metadata = self.stt_service.transcribe_audio(audio_path, self.job_id)
            
            # Analyze results
            self.results["stt_results"] = {
                "success": True,
                "total_entries": len(transcript_result.entries),
                "total_duration": transcript_result.total_duration,
                "language": transcript_result.language,
                "confidence": transcript_result.confidence,
                "processing_metadata": metadata,
                "sample_entries": [
                    {
                        "start_time": entry.start_time,
                        "end_time": entry.end_time,
                        "duration": entry.end_time - entry.start_time,
                        "text": entry.text,
                        "confidence": entry.confidence
                    }
                    for entry in transcript_result.entries[:5]  # First 5 entries
                ]
            }
            
            logger.info(f"✅ STT processing successful:")
            logger.info(f"  - Entries: {len(transcript_result.entries)}")
            logger.info(f"  - Duration: {transcript_result.total_duration:.1f}s")
            logger.info(f"  - Language: {transcript_result.language}")
            confidence_str = f"{transcript_result.confidence:.3f}" if transcript_result.confidence else "N/A"
            logger.info(f"  - Confidence: {confidence_str}")
            logger.info(f"  - Method: {metadata.get('transcription_method', 'unknown')}")
            logger.info(f"  - Cost: ${metadata.get('estimated_cost_usd', 0):.4f}")
            
            # Check for subtitle files
            srt_path = metadata.get("srt_path")
            vtt_path = metadata.get("vtt_path")
            
            if srt_path and Path(srt_path).exists():
                logger.info(f"  - SRT file: {srt_path}")
                self.results["files_created"].append(srt_path)
            
            if vtt_path and Path(vtt_path).exists():
                logger.info(f"  - VTT file: {vtt_path}")
                self.results["files_created"].append(vtt_path)
            
            # Show sample transcript
            logger.info("Sample transcript entries:")
            for i, entry in enumerate(transcript_result.entries[:3]):
                logger.info(f"  {i+1}. [{entry.start_time:.1f}s-{entry.end_time:.1f}s] {entry.text}")
            
            return True
            
        except Exception as e:
            self.results["errors"].append(f"STT processing failed: {str(e)}")
            logger.error(f"❌ STT processing failed: {str(e)}")
            return False
    
    def test_phrase_management(self) -> bool:
        """Test phrase management"""
        logger.info("=== Testing Phrase Management ===")
        
        try:
            # Get phrases for current language
            phrases = self.phrase_manager.get_phrases_for_language(settings.stt.language_code)
            
            # Test validation
            validation = self.phrase_manager.validate_config()
            
            self.results["phrase_management"] = {
                "success": True,
                "language_code": settings.stt.language_code,
                "phrases_loaded": len(phrases),
                "validation_passed": validation["valid"],
                "categories": self.phrase_manager.get_all_categories(),
                "sample_phrases": phrases[:10]
            }
            
            logger.info(f"✅ Phrase management:")
            logger.info(f"  - Language: {settings.stt.language_code}")
            logger.info(f"  - Phrases loaded: {len(phrases)}")
            logger.info(f"  - Validation: {'✅' if validation['valid'] else '❌'}")
            logger.info(f"  - Categories: {len(self.phrase_manager.get_all_categories())}")
            
            return True
            
        except Exception as e:
            self.results["errors"].append(f"Phrase management failed: {str(e)}")
            logger.error(f"❌ Phrase management failed: {str(e)}")
            return False
    
    def _check_stt_compatibility(self, audio: AudioSegment, size_mb: float) -> bool:
        """Check if audio is compatible with Google STT"""
        return (
            size_mb <= 10.0 and
            audio.frame_rate >= 8000 and
            audio.frame_rate <= 48000 and
            audio.sample_width == 2 and
            audio.channels == 1
        )
    
    def run_full_test(self, skip_stt: bool = False) -> bool:
        """Run complete test workflow"""
        logger.info("Starting YouTube Extraction Test")
        logger.info("=" * 60)
        logger.info(f"URL: {self.youtube_url}")
        logger.info(f"Job ID: {self.job_id}")
        
        tests = [
            ("YouTube Download", self.test_youtube_download),
            ("Audio Processing", self.test_audio_processing),
            ("Audio Chunking", self.test_chunking),
            ("Phrase Management", self.test_phrase_management),
        ]
        
        if not skip_stt:
            tests.append(("STT Processing", self.test_stt_processing))
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            logger.info(f"\n{test_name}...")
            try:
                if test_func():
                    passed += 1
                    logger.info(f"✅ {test_name} PASSED")
                else:
                    logger.error(f"❌ {test_name} FAILED")
            except Exception as e:
                logger.error(f"❌ {test_name} FAILED with exception: {e}")
                self.results["errors"].append(f"{test_name} failed: {str(e)}")
        
        # Overall result
        self.results["success"] = passed == total
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Overall: {passed}/{total} tests passed")
        
        if self.results["success"]:
            logger.info("🎉 ALL TESTS PASSED!")
        else:
            logger.error("❌ Some tests failed")
            logger.error("Errors:")
            for error in self.results["errors"]:
                logger.error(f"  - {error}")
        
        return self.results["success"]
    
    def save_results(self, output_file: str = None):
        """Save test results to JSON file"""
        if not output_file:
            output_file = f"{self.job_id}_test_results.json"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Test results saved to: {output_file}")
            
        except Exception as e:
            logger.error(f"Failed to save results: {e}")
    
    def cleanup(self):
        """Clean up test files"""
        logger.info("Cleaning up test files...")
        
        cleaned = 0
        for file_path in self.results["files_created"]:
            try:
                if Path(file_path).exists():
                    Path(file_path).unlink()
                    cleaned += 1
            except Exception as e:
                logger.warning(f"Could not delete {file_path}: {e}")
        
        logger.info(f"Cleaned up {cleaned} files")


def main():
    parser = argparse.ArgumentParser(description="Test YouTube extraction workflow")
    parser.add_argument("--url", default="https://youtu.be/wl7zlu4YoA4", help="YouTube URL to test")
    parser.add_argument("--job-id", help="Custom job ID")
    parser.add_argument("--skip-stt", action="store_true", help="Skip STT processing")
    parser.add_argument("--output", help="Output file for test results")
    parser.add_argument("--cleanup", action="store_true", help="Clean up files after testing")
    
    args = parser.parse_args()
    
    # Create test instance
    test = YouTubeExtractionTest(args.url, args.job_id)
    
    try:
        # Run tests
        success = test.run_full_test(skip_stt=args.skip_stt)
        
        # Save results
        if args.output:
            test.save_results(args.output)
        
        # Cleanup if requested
        if args.cleanup:
            test.cleanup()
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        test.cleanup()
        sys.exit(130)
    except Exception as e:
        logger.error(f"Test failed with unexpected error: {e}")
        test.cleanup()
        sys.exit(1)


if __name__ == "__main__":
    main()