#!/usr/bin/env python3
"""
Validation script for the chunking system - tests the complete workflow
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any
import tempfile
import json
import argparse

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ingest.audio_extractor import AudioExtractor
from app.services.stt.google_stt import GoogleSTTService
from app.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def validate_chunk_sizes(chunk_files: List[str], google_limit_mb: float = 10.0) -> Dict[str, Any]:
    """Validate that all chunks meet size requirements"""
    validation_results = {
        "total_chunks": len(chunk_files),
        "valid_chunks": 0,
        "oversized_chunks": [],
        "undersized_chunks": [],
        "total_size_mb": 0.0,
        "largest_chunk_mb": 0.0,
        "smallest_chunk_mb": float('inf'),
        "average_chunk_mb": 0.0
    }
    
    for i, chunk_file in enumerate(chunk_files):
        chunk_path = Path(chunk_file)
        
        if not chunk_path.exists():
            logger.warning(f"Chunk file does not exist: {chunk_file}")
            continue
            
        chunk_size_mb = chunk_path.stat().st_size / (1024 * 1024)
        validation_results["total_size_mb"] += chunk_size_mb
        
        # Track size statistics
        validation_results["largest_chunk_mb"] = max(validation_results["largest_chunk_mb"], chunk_size_mb)
        validation_results["smallest_chunk_mb"] = min(validation_results["smallest_chunk_mb"], chunk_size_mb)
        
        # Check size limits
        if chunk_size_mb > google_limit_mb:
            validation_results["oversized_chunks"].append({
                "file": chunk_file,
                "size_mb": chunk_size_mb,
                "excess_mb": chunk_size_mb - google_limit_mb
            })
        elif chunk_size_mb < 0.001:  # Less than 1KB
            validation_results["undersized_chunks"].append({
                "file": chunk_file,
                "size_mb": chunk_size_mb
            })
        else:
            validation_results["valid_chunks"] += 1
    
    if validation_results["total_chunks"] > 0:
        validation_results["average_chunk_mb"] = validation_results["total_size_mb"] / validation_results["total_chunks"]
        
    if validation_results["smallest_chunk_mb"] == float('inf'):
        validation_results["smallest_chunk_mb"] = 0.0
    
    return validation_results


def validate_audio_quality(chunk_files: List[str]) -> Dict[str, Any]:
    """Validate audio quality of chunks"""
    from pydub import AudioSegment
    
    quality_results = {
        "total_duration_s": 0.0,
        "chunks_analyzed": 0,
        "sample_rates": set(),
        "channels": set(),
        "sample_widths": set(),
        "short_chunks": [],
        "audio_errors": []
    }
    
    for chunk_file in chunk_files:
        try:
            audio = AudioSegment.from_wav(chunk_file)
            duration_s = len(audio) / 1000.0
            
            quality_results["total_duration_s"] += duration_s
            quality_results["chunks_analyzed"] += 1
            quality_results["sample_rates"].add(audio.frame_rate)
            quality_results["channels"].add(audio.channels)
            quality_results["sample_widths"].add(audio.sample_width)
            
            # Check for very short chunks
            if duration_s < 5.0:
                quality_results["short_chunks"].append({
                    "file": chunk_file,
                    "duration_s": duration_s
                })
                
        except Exception as e:
            quality_results["audio_errors"].append({
                "file": chunk_file,
                "error": str(e)
            })
    
    # Convert sets to lists for JSON serialization
    quality_results["sample_rates"] = list(quality_results["sample_rates"])
    quality_results["channels"] = list(quality_results["channels"])
    quality_results["sample_widths"] = list(quality_results["sample_widths"])
    
    return quality_results


def test_chunking_with_file(audio_file: str, job_id: str = "validation_test") -> Dict[str, Any]:
    """Test chunking with a specific audio file"""
    logger.info(f"Testing chunking with file: {audio_file}")
    
    audio_path = Path(audio_file)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file}")
    
    # Get original file info
    original_size_mb = audio_path.stat().st_size / (1024 * 1024)
    
    try:
        from pydub import AudioSegment
        original_audio = AudioSegment.from_file(str(audio_path))
        original_duration_s = len(original_audio) / 1000.0
    except Exception as e:
        logger.warning(f"Could not analyze original audio: {str(e)}")
        original_duration_s = None
    
    # Test chunking
    extractor = AudioExtractor()
    chunk_files = extractor.split_audio_if_needed(str(audio_path), job_id, max_chunk_size_mb=8.0)
    
    # Validate results
    size_validation = validate_chunk_sizes(chunk_files)
    quality_validation = validate_audio_quality(chunk_files)
    
    # Compile results
    results = {
        "original_file": str(audio_path),
        "original_size_mb": original_size_mb,
        "original_duration_s": original_duration_s,
        "chunks_created": len(chunk_files),
        "chunk_files": chunk_files,
        "size_validation": size_validation,
        "quality_validation": quality_validation,
        "chunking_successful": len(size_validation["oversized_chunks"]) == 0,
        "duration_preserved": abs(quality_validation["total_duration_s"] - (original_duration_s or 0)) < 5.0 if original_duration_s else None
    }
    
    return results


def test_stt_integration(chunk_files: List[str], job_id: str = "stt_validation") -> Dict[str, Any]:
    """Test STT integration with chunks"""
    logger.info(f"Testing STT integration with {len(chunk_files)} chunks")
    
    stt_service = GoogleSTTService()
    
    # Test chunk file detection
    if chunk_files:
        audio_path = Path(chunk_files[0]).parent / f"{job_id}_audio.wav"
        detected_chunks = stt_service._find_chunk_files(audio_path, job_id)
        
        chunk_validation = {
            "expected_chunks": len(chunk_files),
            "detected_chunks": len(detected_chunks),
            "all_chunks_detected": len(detected_chunks) == len(chunk_files),
            "chunk_order_correct": detected_chunks == sorted(chunk_files),
            "chunk_validation_passed": [],
            "chunk_validation_failed": []
        }
        
        # Validate each chunk for STT readiness
        for chunk_file in chunk_files:
            try:
                chunk_path = Path(chunk_file)
                chunk_size_mb = chunk_path.stat().st_size / (1024 * 1024)
                
                # Basic validations that STT service performs
                validations = {
                    "file_exists": chunk_path.exists(),
                    "size_acceptable": chunk_size_mb > 0.001,
                    "size_under_limit": chunk_size_mb <= 10.0,
                    "audio_readable": True
                }
                
                # Try to read audio
                try:
                    from pydub import AudioSegment
                    audio = AudioSegment.from_wav(chunk_file)
                    validations["audio_duration_ok"] = len(audio) / 1000.0 > 0.1
                except Exception:
                    validations["audio_readable"] = False
                    validations["audio_duration_ok"] = False
                
                if all(validations.values()):
                    chunk_validation["chunk_validation_passed"].append(chunk_file)
                else:
                    chunk_validation["chunk_validation_failed"].append({
                        "file": chunk_file,
                        "validations": validations
                    })
                    
            except Exception as e:
                chunk_validation["chunk_validation_failed"].append({
                    "file": chunk_file,
                    "error": str(e)
                })
        
        return chunk_validation
    
    return {"error": "No chunks to validate"}


def generate_report(results: Dict[str, Any], output_file: str = None) -> str:
    """Generate a validation report"""
    report = []
    report.append("CHUNKING SYSTEM VALIDATION REPORT")
    report.append("=" * 50)
    report.append("")
    
    # Original file info
    report.append(f"Original File: {results['original_file']}")
    report.append(f"Original Size: {results['original_size_mb']:.2f} MB")
    if results['original_duration_s']:
        report.append(f"Original Duration: {results['original_duration_s']:.1f} seconds")
    report.append("")
    
    # Chunking results
    report.append(f"Chunks Created: {results['chunks_created']}")
    report.append(f"Chunking Successful: {'✅' if results['chunking_successful'] else '❌'}")
    if results['duration_preserved'] is not None:
        report.append(f"Duration Preserved: {'✅' if results['duration_preserved'] else '❌'}")
    report.append("")
    
    # Size validation
    size_val = results['size_validation']
    report.append("SIZE VALIDATION:")
    report.append(f"  Total Chunks: {size_val['total_chunks']}")
    report.append(f"  Valid Chunks: {size_val['valid_chunks']}")
    report.append(f"  Total Size: {size_val['total_size_mb']:.2f} MB")
    report.append(f"  Average Chunk Size: {size_val['average_chunk_mb']:.2f} MB")
    report.append(f"  Largest Chunk: {size_val['largest_chunk_mb']:.2f} MB")
    report.append(f"  Smallest Chunk: {size_val['smallest_chunk_mb']:.2f} MB")
    
    if size_val['oversized_chunks']:
        report.append(f"  ❌ Oversized Chunks: {len(size_val['oversized_chunks'])}")
        for chunk in size_val['oversized_chunks']:
            report.append(f"    - {Path(chunk['file']).name}: {chunk['size_mb']:.2f} MB (excess: {chunk['excess_mb']:.2f} MB)")
    else:
        report.append("  ✅ No oversized chunks")
    
    if size_val['undersized_chunks']:
        report.append(f"  ⚠️ Undersized Chunks: {len(size_val['undersized_chunks'])}")
    report.append("")
    
    # Quality validation
    quality_val = results['quality_validation']
    report.append("QUALITY VALIDATION:")
    report.append(f"  Total Duration: {quality_val['total_duration_s']:.1f} seconds")
    report.append(f"  Chunks Analyzed: {quality_val['chunks_analyzed']}")
    report.append(f"  Sample Rates: {quality_val['sample_rates']}")
    report.append(f"  Channels: {quality_val['channels']}")
    report.append(f"  Sample Widths: {quality_val['sample_widths']}")
    
    if quality_val['short_chunks']:
        report.append(f"  ⚠️ Short Chunks: {len(quality_val['short_chunks'])}")
        for chunk in quality_val['short_chunks']:
            report.append(f"    - {Path(chunk['file']).name}: {chunk['duration_s']:.1f}s")
    
    if quality_val['audio_errors']:
        report.append(f"  ❌ Audio Errors: {len(quality_val['audio_errors'])}")
    report.append("")
    
    # STT Integration (if available)
    if 'stt_validation' in results:
        stt_val = results['stt_validation']
        report.append("STT INTEGRATION:")
        report.append(f"  Expected Chunks: {stt_val['expected_chunks']}")
        report.append(f"  Detected Chunks: {stt_val['detected_chunks']}")
        report.append(f"  All Chunks Detected: {'✅' if stt_val['all_chunks_detected'] else '❌'}")
        report.append(f"  Chunk Order Correct: {'✅' if stt_val['chunk_order_correct'] else '❌'}")
        report.append(f"  Validation Passed: {len(stt_val['chunk_validation_passed'])}")
        report.append(f"  Validation Failed: {len(stt_val['chunk_validation_failed'])}")
        report.append("")
    
    # Summary
    report.append("SUMMARY:")
    overall_success = (
        results['chunking_successful'] and 
        (results['duration_preserved'] if results['duration_preserved'] is not None else True) and
        len(size_val['oversized_chunks']) == 0 and
        len(quality_val['audio_errors']) == 0
    )
    report.append(f"Overall Status: {'✅ PASSED' if overall_success else '❌ FAILED'}")
    
    report_text = "\n".join(report)
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(report_text)
        logger.info(f"Report saved to: {output_file}")
    
    return report_text


def main():
    parser = argparse.ArgumentParser(description="Validate chunking system")
    parser.add_argument("audio_file", help="Path to audio file to test")
    parser.add_argument("--job-id", default="validation_test", help="Job ID for testing")
    parser.add_argument("--output", help="Output file for report")
    parser.add_argument("--test-stt", action="store_true", help="Test STT integration")
    parser.add_argument("--cleanup", action="store_true", help="Clean up chunks after testing")
    
    args = parser.parse_args()
    
    try:
        # Test chunking
        results = test_chunking_with_file(args.audio_file, args.job_id)
        
        # Test STT integration if requested
        if args.test_stt:
            stt_results = test_stt_integration(results['chunk_files'], args.job_id)
            results['stt_validation'] = stt_results
        
        # Generate report
        report = generate_report(results, args.output)
        print(report)
        
        # Cleanup if requested
        if args.cleanup:
            for chunk_file in results['chunk_files']:
                if Path(chunk_file).exists():
                    Path(chunk_file).unlink()
            logger.info("Cleaned up chunk files")
        
        # Exit with appropriate code
        sys.exit(0 if results['chunking_successful'] else 1)
        
    except Exception as e:
        logger.error(f"Validation failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()