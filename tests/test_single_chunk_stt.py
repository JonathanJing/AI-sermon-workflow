#!/usr/bin/env python3
"""
Test script for single chunk STT conversion
Tests the complete pipeline from audio chunk to transcription
"""

import os
import sys
import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional
import tempfile
import argparse

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


def create_test_chunk(source_type: str = "youtube", source_url: str = None, 
                     duration_s: int = 30, job_id: str = "test_single_chunk") -> Optional[str]:
    """Create a test audio chunk"""
    logger.info(f"Creating test chunk from {source_type}")
    
    if source_type == "youtube" and source_url:
        # Download from YouTube and extract a chunk
        try:
            downloader = YouTubeDownloader()
            audio_path = downloader.download_audio(source_url, f"{job_id}_source")
            
            if not audio_path:
                logger.error("Failed to download YouTube audio")
                return None
                
            # Load audio and extract a chunk
            audio = AudioSegment.from_file(audio_path)
            
            # Extract first 30 seconds (or specified duration)
            chunk_duration_ms = min(duration_s * 1000, len(audio))
            chunk = audio[:chunk_duration_ms]
            
            # Process for STT
            extractor = AudioExtractor()
            processed_chunk = extractor._process_for_stt(chunk, job_id, target_size_mb=8.0)
            
            # Save chunk
            chunk_path = Path(extractor.output_path) / f"{job_id}_chunk.wav"
            processed_chunk.export(str(chunk_path), format="wav")
            
            # Cleanup original
            if Path(audio_path).exists():
                Path(audio_path).unlink()
                
            logger.info(f"Created chunk: {chunk_path} ({chunk_duration_ms/1000:.1f}s)")
            return str(chunk_path)
            
        except Exception as e:
            logger.error(f"Failed to create YouTube chunk: {str(e)}")
            return None
    
    elif source_type == "synthetic":
        # Create synthetic audio chunk
        try:
            from pydub.generators import Sine
            
            # Create a sine wave tone
            tone = Sine(440).to_audio_segment(duration=duration_s * 1000)
            
            # Set proper audio properties
            tone = tone.set_frame_rate(16000)
            tone = tone.set_channels(1)
            tone = tone.set_sample_width(2)  # 16-bit
            
            # Save chunk
            extractor = AudioExtractor()
            chunk_path = Path(extractor.output_path) / f"{job_id}_synthetic_chunk.wav"
            tone.export(str(chunk_path), format="wav")
            
            logger.info(f"Created synthetic chunk: {chunk_path} ({duration_s}s)")
            return str(chunk_path)
            
        except Exception as e:
            logger.error(f"Failed to create synthetic chunk: {str(e)}")
            return None
    
    else:
        logger.error(f"Unknown source type: {source_type}")
        return None


def validate_chunk_properties(chunk_path: str) -> Dict[str, Any]:
    """Validate audio chunk properties for STT"""
    logger.info(f"Validating chunk properties: {chunk_path}")
    
    validation = {
        "file_exists": False,
        "file_size_mb": 0.0,
        "sample_rate": 0,
        "channels": 0,
        "sample_width": 0,
        "duration_s": 0.0,
        "google_stt_compatible": False,
        "issues": []
    }
    
    try:
        chunk_path_obj = Path(chunk_path)
        
        # Check file existence
        if not chunk_path_obj.exists():
            validation["issues"].append("File does not exist")
            return validation
        
        validation["file_exists"] = True
        validation["file_size_mb"] = chunk_path_obj.stat().st_size / (1024 * 1024)
        
        # Load audio
        audio = AudioSegment.from_wav(chunk_path)
        validation["sample_rate"] = audio.frame_rate
        validation["channels"] = audio.channels
        validation["sample_width"] = audio.sample_width
        validation["duration_s"] = len(audio) / 1000.0
        
        # Check Google STT compatibility
        if validation["file_size_mb"] > 10.0:
            validation["issues"].append(f"File too large: {validation['file_size_mb']:.2f}MB > 10MB")
        
        if validation["sample_rate"] < 8000 or validation["sample_rate"] > 48000:
            validation["issues"].append(f"Sample rate out of range: {validation['sample_rate']}Hz (8-48kHz required)")
        
        if validation["sample_width"] != 2:  # 16-bit
            validation["issues"].append(f"Sample width not 16-bit: {validation['sample_width'] * 8}-bit")
        
        if validation["channels"] != 1:
            validation["issues"].append(f"Not mono: {validation['channels']} channels")
        
        if validation["duration_s"] < 0.1:
            validation["issues"].append(f"Too short: {validation['duration_s']:.1f}s")
        
        validation["google_stt_compatible"] = len(validation["issues"]) == 0
        
        logger.info(f"Chunk validation: {validation['google_stt_compatible']}")
        if validation["issues"]:
            for issue in validation["issues"]:
                logger.warning(f"  - {issue}")
        
        return validation
        
    except Exception as e:
        validation["issues"].append(f"Validation error: {str(e)}")
        logger.error(f"Chunk validation failed: {str(e)}")
        return validation


def test_stt_conversion(chunk_path: str, job_id: str = "test_stt") -> Dict[str, Any]:
    """Test STT conversion on a single chunk"""
    logger.info(f"Testing STT conversion: {chunk_path}")
    
    result = {
        "success": False,
        "transcript_entries": [],
        "total_duration": 0.0,
        "confidence": None,
        "language": None,
        "processing_metadata": {},
        "error": None
    }
    
    try:
        # Initialize STT service
        stt_service = GoogleSTTService()
        
        # Check if Google STT is available
        if not stt_service.client:
            result["error"] = "Google STT client not initialized (check credentials)"
            logger.error(result["error"])
            return result
        
        # Test transcription
        logger.info("Starting STT transcription...")
        transcript_result, processing_metadata = stt_service._transcribe_single_file(chunk_path, job_id)
        
        # Extract results
        result["success"] = True
        result["transcript_entries"] = [
            {
                "start_time": entry.start_time,
                "end_time": entry.end_time,
                "text": entry.text,
                "confidence": entry.confidence
            }
            for entry in transcript_result.entries
        ]
        result["total_duration"] = transcript_result.total_duration
        result["confidence"] = transcript_result.confidence
        result["language"] = transcript_result.language
        result["processing_metadata"] = processing_metadata
        
        logger.info(f"STT conversion successful:")
        logger.info(f"  - Entries: {len(result['transcript_entries'])}")
        logger.info(f"  - Duration: {result['total_duration']:.1f}s")
        logger.info(f"  - Confidence: {result['confidence']:.3f if result['confidence'] else 'N/A'}")
        logger.info(f"  - Method: {processing_metadata.get('transcription_method', 'unknown')}")
        
        # Log transcript entries
        for i, entry in enumerate(result["transcript_entries"]):
            logger.info(f"  Entry {i+1}: [{entry['start_time']:.1f}s-{entry['end_time']:.1f}s] {entry['text']}")
        
        # Check for subtitle files
        srt_path = processing_metadata.get("srt_path")
        vtt_path = processing_metadata.get("vtt_path")
        
        if srt_path and Path(srt_path).exists():
            logger.info(f"✅ SRT file created: {srt_path}")
            result["srt_file"] = srt_path
        else:
            logger.warning("⚠️ No SRT file created")
        
        if vtt_path and Path(vtt_path).exists():
            logger.info(f"✅ VTT file created: {vtt_path}")
            result["vtt_file"] = vtt_path
        else:
            logger.warning("⚠️ No VTT file created")
        
        return result
        
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"STT conversion failed: {str(e)}")
        return result


def test_phrase_management(language_code: str = "cmn-Hans-CN") -> Dict[str, Any]:
    """Test phrase management for STT"""
    logger.info(f"Testing phrase management for language: {language_code}")
    
    result = {
        "phrases_loaded": 0,
        "categories": [],
        "sample_phrases": [],
        "validation_passed": False
    }
    
    try:
        phrase_manager = PhraseManager()
        
        # Test phrase loading
        phrases = phrase_manager.get_phrases_for_language(language_code)
        result["phrases_loaded"] = len(phrases)
        result["sample_phrases"] = phrases[:10]  # First 10 phrases
        
        # Test categories
        categories = phrase_manager.get_all_categories()
        result["categories"] = categories
        
        # Test validation
        validation = phrase_manager.validate_config()
        result["validation_passed"] = validation["valid"]
        
        logger.info(f"Phrase management test:")
        logger.info(f"  - Phrases loaded: {result['phrases_loaded']}")
        logger.info(f"  - Categories: {len(result['categories'])}")
        logger.info(f"  - Validation: {'✅' if result['validation_passed'] else '❌'}")
        logger.info(f"  - Sample phrases: {result['sample_phrases'][:5]}")
        
        return result
        
    except Exception as e:
        logger.error(f"Phrase management test failed: {str(e)}")
        result["error"] = str(e)
        return result


def run_comprehensive_test(source_type: str = "youtube", 
                         source_url: str = "https://youtu.be/QBiaM7BXsY4",
                         duration_s: int = 30,
                         job_id: str = "comprehensive_test") -> Dict[str, Any]:
    """Run comprehensive single chunk STT test"""
    logger.info("Starting comprehensive single chunk STT test")
    logger.info("=" * 60)
    
    comprehensive_result = {
        "test_timestamp": str(Path(__file__).parent.parent / "data" / "processed"),
        "job_id": job_id,
        "source_type": source_type,
        "source_url": source_url,
        "chunk_creation": {},
        "chunk_validation": {},
        "stt_conversion": {},
        "phrase_management": {},
        "overall_success": False
    }
    
    try:
        # 1. Create test chunk
        logger.info("Step 1: Creating test chunk...")
        chunk_path = create_test_chunk(source_type, source_url, duration_s, job_id)
        
        if not chunk_path:
            comprehensive_result["chunk_creation"]["error"] = "Failed to create test chunk"
            return comprehensive_result
        
        comprehensive_result["chunk_creation"]["success"] = True
        comprehensive_result["chunk_creation"]["chunk_path"] = chunk_path
        
        # 2. Validate chunk properties
        logger.info("Step 2: Validating chunk properties...")
        validation = validate_chunk_properties(chunk_path)
        comprehensive_result["chunk_validation"] = validation
        
        if not validation["google_stt_compatible"]:
            logger.error("Chunk validation failed - not Google STT compatible")
            return comprehensive_result
        
        # 3. Test STT conversion
        logger.info("Step 3: Testing STT conversion...")
        stt_result = test_stt_conversion(chunk_path, job_id)
        comprehensive_result["stt_conversion"] = stt_result
        
        # 4. Test phrase management
        logger.info("Step 4: Testing phrase management...")
        phrase_result = test_phrase_management(settings.stt.language_code)
        comprehensive_result["phrase_management"] = phrase_result
        
        # Determine overall success
        comprehensive_result["overall_success"] = (
            comprehensive_result["chunk_creation"].get("success", False) and
            comprehensive_result["chunk_validation"]["google_stt_compatible"] and
            comprehensive_result["stt_conversion"]["success"] and
            comprehensive_result["phrase_management"]["validation_passed"]
        )
        
        logger.info("=" * 60)
        if comprehensive_result["overall_success"]:
            logger.info("🎉 COMPREHENSIVE TEST PASSED!")
        else:
            logger.error("❌ COMPREHENSIVE TEST FAILED!")
        
        return comprehensive_result
        
    except Exception as e:
        logger.error(f"Comprehensive test failed: {str(e)}")
        comprehensive_result["error"] = str(e)
        return comprehensive_result
    
    finally:
        # Cleanup
        if "chunk_path" in comprehensive_result.get("chunk_creation", {}):
            chunk_path = comprehensive_result["chunk_creation"]["chunk_path"]
            if Path(chunk_path).exists():
                Path(chunk_path).unlink()
                logger.info(f"Cleaned up: {chunk_path}")


def generate_test_report(result: Dict[str, Any], output_file: str = None) -> str:
    """Generate a test report"""
    report = []
    report.append("SINGLE CHUNK STT CONVERSION TEST REPORT")
    report.append("=" * 50)
    report.append("")
    
    # Test details
    report.append(f"Job ID: {result['job_id']}")
    report.append(f"Source Type: {result['source_type']}")
    if result.get('source_url'):
        report.append(f"Source URL: {result['source_url']}")
    report.append(f"Overall Success: {'✅ PASSED' if result['overall_success'] else '❌ FAILED'}")
    report.append("")
    
    # Chunk creation
    chunk_creation = result.get("chunk_creation", {})
    report.append("CHUNK CREATION:")
    if chunk_creation.get("success"):
        report.append(f"  ✅ Chunk created successfully")
        report.append(f"  Path: {chunk_creation.get('chunk_path', 'N/A')}")
    else:
        report.append(f"  ❌ Failed: {chunk_creation.get('error', 'Unknown error')}")
    report.append("")
    
    # Chunk validation
    validation = result.get("chunk_validation", {})
    report.append("CHUNK VALIDATION:")
    report.append(f"  File Size: {validation.get('file_size_mb', 0):.2f} MB")
    report.append(f"  Sample Rate: {validation.get('sample_rate', 0)} Hz")
    report.append(f"  Channels: {validation.get('channels', 0)}")
    report.append(f"  Duration: {validation.get('duration_s', 0):.1f} seconds")
    report.append(f"  Google STT Compatible: {'✅' if validation.get('google_stt_compatible') else '❌'}")
    
    if validation.get('issues'):
        report.append("  Issues:")
        for issue in validation['issues']:
            report.append(f"    - {issue}")
    report.append("")
    
    # STT conversion
    stt_result = result.get("stt_conversion", {})
    report.append("STT CONVERSION:")
    if stt_result.get("success"):
        report.append(f"  ✅ Conversion successful")
        report.append(f"  Entries: {len(stt_result.get('transcript_entries', []))}")
        report.append(f"  Duration: {stt_result.get('total_duration', 0):.1f}s")
        report.append(f"  Confidence: {stt_result.get('confidence', 'N/A')}")
        report.append(f"  Language: {stt_result.get('language', 'N/A')}")
        
        # Show transcript entries
        entries = stt_result.get('transcript_entries', [])
        if entries:
            report.append("  Transcript:")
            for i, entry in enumerate(entries):
                report.append(f"    {i+1}. [{entry['start_time']:.1f}s-{entry['end_time']:.1f}s] {entry['text']}")
    else:
        report.append(f"  ❌ Failed: {stt_result.get('error', 'Unknown error')}")
    report.append("")
    
    # Phrase management
    phrase_result = result.get("phrase_management", {})
    report.append("PHRASE MANAGEMENT:")
    report.append(f"  Phrases Loaded: {phrase_result.get('phrases_loaded', 0)}")
    report.append(f"  Categories: {len(phrase_result.get('categories', []))}")
    report.append(f"  Validation: {'✅' if phrase_result.get('validation_passed') else '❌'}")
    report.append("")
    
    # Summary
    report.append("SUMMARY:")
    report.append(f"Test Status: {'✅ PASSED' if result['overall_success'] else '❌ FAILED'}")
    
    report_text = "\n".join(report)
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(report_text)
        logger.info(f"Report saved to: {output_file}")
    
    return report_text


def main():
    parser = argparse.ArgumentParser(description="Test single chunk STT conversion")
    parser.add_argument("--source", choices=["youtube", "synthetic"], default="youtube",
                       help="Source type for test audio")
    parser.add_argument("--url", default="https://youtu.be/QBiaM7BXsY4",
                       help="YouTube URL for testing")
    parser.add_argument("--duration", type=int, default=30,
                       help="Duration in seconds for test chunk")
    parser.add_argument("--job-id", default="single_chunk_test",
                       help="Job ID for testing")
    parser.add_argument("--output", help="Output file for report")
    parser.add_argument("--json", help="Output JSON results file")
    
    args = parser.parse_args()
    
    try:
        # Run comprehensive test
        result = run_comprehensive_test(
            source_type=args.source,
            source_url=args.url,
            duration_s=args.duration,
            job_id=args.job_id
        )
        
        # Generate report
        report = generate_test_report(result, args.output)
        print(report)
        
        # Save JSON results if requested
        if args.json:
            with open(args.json, 'w') as f:
                json.dump(result, f, indent=2)
            logger.info(f"JSON results saved to: {args.json}")
        
        # Exit with appropriate code
        sys.exit(0 if result["overall_success"] else 1)
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()