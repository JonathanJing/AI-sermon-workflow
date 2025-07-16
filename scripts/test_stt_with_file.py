#!/usr/bin/env python3
"""
Test STT conversion with an existing audio file
"""

import sys
import logging
from pathlib import Path
import argparse

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ingest.audio_extractor import AudioExtractor
from app.services.stt.google_stt import GoogleSTTService
from pydub import AudioSegment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_stt_with_file(audio_file: str, job_id: str = "file_test", max_duration_s: int = 60):
    """Test STT conversion with existing audio file"""
    
    audio_path = Path(audio_file)
    if not audio_path.exists():
        logger.error(f"❌ Audio file not found: {audio_file}")
        return False
    
    try:
        # 1. Load and validate audio
        logger.info(f"Step 1: Loading audio file: {audio_file}")
        original_audio = AudioSegment.from_file(str(audio_path))
        original_duration_s = len(original_audio) / 1000
        original_size_mb = audio_path.stat().st_size / (1024 * 1024)
        
        logger.info(f"Original audio: {original_duration_s:.1f}s, {original_size_mb:.2f}MB, {original_audio.frame_rate}Hz")
        
        # Limit duration if needed
        if original_duration_s > max_duration_s:
            logger.info(f"Limiting to first {max_duration_s} seconds")
            audio = original_audio[:max_duration_s * 1000]
        else:
            audio = original_audio
        
        # 2. Process for STT
        logger.info("Step 2: Processing audio for STT...")
        extractor = AudioExtractor()
        processed_audio = extractor._process_for_stt(audio, job_id, target_size_mb=8.0)
        
        # Save processed audio
        processed_path = Path(extractor.output_path) / f"{job_id}_processed.wav"
        processed_audio.export(str(processed_path), format="wav")
        
        # Validate processed audio
        processed_size_mb = processed_path.stat().st_size / (1024 * 1024)
        processed_duration_s = len(processed_audio) / 1000
        
        logger.info(f"Processed audio: {processed_duration_s:.1f}s, {processed_size_mb:.2f}MB, {processed_audio.frame_rate}Hz")
        
        # Check Google STT compatibility
        issues = []
        if processed_size_mb > 10.0:
            issues.append(f"File too large: {processed_size_mb:.2f}MB > 10MB")
        
        if processed_audio.frame_rate < 8000 or processed_audio.frame_rate > 48000:
            issues.append(f"Sample rate out of range: {processed_audio.frame_rate}Hz")
        
        if processed_audio.sample_width != 2:
            issues.append(f"Not 16-bit: {processed_audio.sample_width * 8}-bit")
        
        if processed_audio.channels != 1:
            issues.append(f"Not mono: {processed_audio.channels} channels")
        
        if issues:
            logger.error("❌ Google STT compatibility issues:")
            for issue in issues:
                logger.error(f"  - {issue}")
            return False
        
        logger.info("✅ Audio is Google STT compatible")
        
        # 3. Test STT conversion
        logger.info("Step 3: Testing STT conversion...")
        stt_service = GoogleSTTService()
        
        if not stt_service.client:
            logger.error("❌ Google STT client not available")
            logger.info("Make sure Google Cloud credentials are configured:")
            logger.info("  - Set GOOGLE_APPLICATION_CREDENTIALS environment variable")
            logger.info("  - Or configure credentials in app/config.py")
            return False
        
        # Perform transcription
        transcript_result, metadata = stt_service._transcribe_single_file(str(processed_path), job_id)
        
        # Display results
        logger.info(f"✅ STT conversion successful:")
        logger.info(f"  - Entries: {len(transcript_result.entries)}")
        logger.info(f"  - Duration: {transcript_result.total_duration:.1f}s")
        confidence_str = f"{transcript_result.confidence:.3f}" if transcript_result.confidence else "N/A"
        logger.info(f"  - Confidence: {confidence_str}")
        logger.info(f"  - Language: {transcript_result.language}")
        logger.info(f"  - Method: {metadata.get('transcription_method', 'unknown')}")
        logger.info(f"  - Cost: ${metadata.get('estimated_cost_usd', 0):.4f}")
        
        # Show transcript
        logger.info("Transcript entries:")
        for i, entry in enumerate(transcript_result.entries):
            confidence_str = f" (conf: {entry.confidence:.3f})" if entry.confidence else ""
            logger.info(f"  {i+1}. [{entry.start_time:.1f}s-{entry.end_time:.1f}s] {entry.text}{confidence_str}")
        
        # Check for subtitle files
        srt_path = metadata.get("srt_path")
        vtt_path = metadata.get("vtt_path")
        
        if srt_path and Path(srt_path).exists():
            logger.info(f"✅ SRT file created: {srt_path}")
        else:
            logger.warning("⚠️ No SRT file created")
        
        if vtt_path and Path(vtt_path).exists():
            logger.info(f"✅ VTT file created: {vtt_path}")
        else:
            logger.warning("⚠️ No VTT file created")
        
        # 4. Save results
        logger.info("Step 4: Saving results...")
        
        # Save transcript as JSON
        import json
        transcript_data = {
            "original_file": str(audio_path),
            "job_id": job_id,
            "processing_metadata": metadata,
            "transcript_result": {
                "entries": [
                    {
                        "start_time": entry.start_time,
                        "end_time": entry.end_time,
                        "text": entry.text,
                        "confidence": entry.confidence
                    }
                    for entry in transcript_result.entries
                ],
                "total_duration": transcript_result.total_duration,
                "language": transcript_result.language,
                "confidence": transcript_result.confidence
            }
        }
        
        transcript_json_path = Path(extractor.output_path) / f"{job_id}_transcript.json"
        with open(transcript_json_path, 'w', encoding='utf-8') as f:
            json.dump(transcript_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Results saved:")
        logger.info(f"  - Processed audio: {processed_path}")
        logger.info(f"  - Transcript JSON: {transcript_json_path}")
        if srt_path:
            logger.info(f"  - SRT subtitles: {srt_path}")
        if vtt_path:
            logger.info(f"  - VTT subtitles: {vtt_path}")
        
        # 5. Cleanup (optional)
        cleanup = input("Clean up processed files? (y/n): ").lower() == 'y'
        if cleanup:
            if processed_path.exists():
                processed_path.unlink()
            if transcript_json_path.exists():
                transcript_json_path.unlink()
            logger.info("✅ Cleaned up temporary files")
        
        logger.info("🎉 STT test with file PASSED!")
        return True
        
    except Exception as e:
        logger.error(f"❌ STT test FAILED: {str(e)}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test STT conversion with audio file")
    parser.add_argument("audio_file", help="Path to audio file")
    parser.add_argument("--job-id", default="file_test", help="Job ID for testing")
    parser.add_argument("--max-duration", type=int, default=60, help="Maximum duration in seconds")
    
    args = parser.parse_args()
    
    success = test_stt_with_file(args.audio_file, args.job_id, args.max_duration)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()