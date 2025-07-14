import os
import logging
from typing import Optional, Tuple, Dict, Any
from pathlib import Path
from pydub import AudioSegment
from pydub.utils import which
import ffmpeg
from app.config import settings

logger = logging.getLogger(__name__)


class AudioExtractor:
    """Service for extracting and processing audio from various sources"""
    
    def __init__(self):
        self.output_path = Path(settings.storage.local_path) / "processed"
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        # Check if ffmpeg is available
        if not which("ffmpeg"):
            logger.warning("ffmpeg not found. Audio conversion capabilities may be limited.")
    
    def extract_from_file(self, file_path: str, job_id: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract audio from local file (MP3, MP4, WAV, etc.)
        
        Args:
            file_path: Path to the input file
            job_id: Unique job identifier
            
        Returns:
            Tuple of (processed_audio_path, metadata)
            
        Raises:
            Exception: If extraction fails
        """
        try:
            logger.info(f"Starting audio extraction for job {job_id}: {file_path}")
            
            input_path = Path(file_path)
            if not input_path.exists():
                raise FileNotFoundError(f"Input file not found: {file_path}")
            
            # Get file metadata
            file_size_mb = input_path.stat().st_size / (1024 * 1024)
            
            # Check file size limit
            if file_size_mb > settings.storage.max_file_size_mb:
                raise ValueError(f"File size ({file_size_mb:.2f} MB) exceeds maximum allowed ({settings.storage.max_file_size_mb} MB)")
            
            # Load audio using pydub
            audio = AudioSegment.from_file(str(input_path))
            
            # Get audio metadata
            metadata = {
                "title": input_path.stem,
                "duration_seconds": len(audio) / 1000.0,
                "file_size_mb": file_size_mb,
                "original_format": input_path.suffix.lower().lstrip('.'),
                "sample_rate": audio.frame_rate,
                "channels": audio.channels,
                "frame_rate": audio.frame_rate,
                "sample_width": audio.sample_width
            }
            
            # Validate duration
            if metadata["duration_seconds"] > 7200:  # 2 hours
                raise ValueError(f"Audio duration ({metadata['duration_seconds']}s) exceeds maximum allowed (7200s)")
            
            logger.info(f"Audio metadata - Duration: {metadata['duration_seconds']:.2f}s, "
                       f"Sample Rate: {metadata['sample_rate']}Hz, Channels: {metadata['channels']}")
            
            # Process audio for STT (convert to optimal format)
            processed_audio = self._process_for_stt(audio, job_id)
            
            # Save processed audio
            output_filename = f"{job_id}_processed.wav"
            output_path = self.output_path / output_filename
            
            processed_audio.export(str(output_path), format="wav")
            
            # Update metadata with processed info
            processed_file_size_mb = output_path.stat().st_size / (1024 * 1024)
            metadata.update({
                "processed_file_size_mb": processed_file_size_mb,
                "processed_format": "wav",
                "processed_sample_rate": processed_audio.frame_rate,
                "processed_channels": processed_audio.channels
            })
            
            logger.info(f"Audio extraction completed: {output_path} ({processed_file_size_mb:.2f} MB)")
            
            return str(output_path), metadata
            
        except Exception as e:
            logger.error(f"Audio extraction failed for job {job_id}: {str(e)}")
            raise Exception(f"Audio extraction failed: {str(e)}")
    
    def _process_for_stt(self, audio: AudioSegment, job_id: str, target_size_mb: float = 9.0) -> AudioSegment:
        """
        Process audio for optimal STT performance with size optimization
        
        Args:
            audio: Input audio segment
            job_id: Job identifier for logging
            target_size_mb: Target file size in MB (default 9MB to stay under 10MB limit)
            
        Returns:
            Processed audio segment
        """
        try:
            logger.info(f"Processing audio for STT optimization (target: {target_size_mb}MB) for job {job_id}")
            
            # Convert to mono if stereo
            if audio.channels > 1:
                logger.info(f"Converting stereo to mono for job {job_id}")
                audio = audio.set_channels(1)
            
            # Start with 16kHz for optimal STT performance
            target_sample_rate = 16000
            if audio.frame_rate != target_sample_rate:
                logger.info(f"Resampling from {audio.frame_rate}Hz to {target_sample_rate}Hz for job {job_id}")
                audio = audio.set_frame_rate(target_sample_rate)
            
            # Normalize audio levels
            audio = audio.normalize()
            
            # Set sample width to 16-bit (2 bytes) for Google STT compatibility
            if audio.sample_width != 2:
                logger.info(f"Converting from {audio.sample_width * 8}-bit to 16-bit for job {job_id}")
                audio = audio.set_sample_width(2)
            
            # Apply noise reduction if available (basic implementation)
            audio = self._apply_basic_noise_reduction(audio)
            
            # Check if we need further compression
            estimated_size_mb = self._estimate_wav_size(audio)
            logger.info(f"Estimated WAV size: {estimated_size_mb:.2f}MB for job {job_id}")
            
            if estimated_size_mb > target_size_mb:
                logger.info(f"Audio too large ({estimated_size_mb:.2f}MB), applying compression for job {job_id}")
                audio = self._compress_audio(audio, job_id, target_size_mb)
            
            return audio
            
        except Exception as e:
            logger.error(f"Audio processing failed for job {job_id}: {str(e)}")
            raise Exception(f"Audio processing failed: {str(e)}")
    
    def _estimate_wav_size(self, audio: AudioSegment) -> float:
        """Estimate WAV file size in MB"""
        # WAV size = sample_rate * channels * sample_width * duration_seconds
        duration_seconds = len(audio) / 1000.0
        bytes_per_sample = audio.sample_width
        total_bytes = audio.frame_rate * audio.channels * bytes_per_sample * duration_seconds
        return total_bytes / (1024 * 1024)
    
    def _compress_audio(self, audio: AudioSegment, job_id: str, target_size_mb: float) -> AudioSegment:
        """
        Compress audio to meet size requirements while maintaining STT quality
        
        Args:
            audio: Input audio segment
            job_id: Job identifier for logging
            target_size_mb: Target file size in MB
            
        Returns:
            Compressed audio segment
        """
        try:
            original_size = self._estimate_wav_size(audio)
            compression_ratio = target_size_mb / original_size
            
            logger.info(f"Compressing audio by ratio {compression_ratio:.2f} for job {job_id}")
            
            if compression_ratio < 0.5:
                # Aggressive compression needed - reduce sample rate
                new_sample_rate = max(8000, int(audio.frame_rate * compression_ratio * 1.2))
                logger.info(f"Reducing sample rate to {new_sample_rate}Hz for job {job_id}")
                audio = audio.set_frame_rate(new_sample_rate)
            elif compression_ratio < 0.8:
                # Moderate compression - slight sample rate reduction
                new_sample_rate = max(12000, int(audio.frame_rate * 0.75))
                logger.info(f"Reducing sample rate to {new_sample_rate}Hz for job {job_id}")
                audio = audio.set_frame_rate(new_sample_rate)
            
            # Apply dynamic range compression to reduce file size
            audio = audio.compress_dynamic_range(threshold=-20.0, ratio=4.0, attack=5.0, release=50.0)
            
            # Final size check
            final_size = self._estimate_wav_size(audio)
            logger.info(f"Compressed audio size: {final_size:.2f}MB (target: {target_size_mb}MB) for job {job_id}")
            
            return audio
            
        except Exception as e:
            logger.warning(f"Audio compression failed for job {job_id}, using original: {str(e)}")
            return audio
    
    def _apply_basic_noise_reduction(self, audio: AudioSegment) -> AudioSegment:
        """
        Apply basic noise reduction
        
        Args:
            audio: Input audio segment
            
        Returns:
            Processed audio with reduced noise
        """
        try:
            # Basic noise gate - remove quiet background noise
            # This is a simple implementation; more sophisticated noise reduction
            # would require additional libraries like noisereduce
            
            # Calculate silence threshold (10% of max amplitude)
            silence_threshold = audio.max_possible_amplitude * 0.1
            
            # Apply simple noise gate
            chunks = audio[::100]  # Sample every 100ms
            non_silent_chunks = []
            
            for i, chunk in enumerate(chunks):
                if chunk.rms > silence_threshold:
                    start_idx = i * 100
                    end_idx = min((i + 1) * 100, len(audio))
                    non_silent_chunks.append(audio[start_idx:end_idx])
            
            if non_silent_chunks:
                # Rejoin non-silent chunks
                return sum(non_silent_chunks)
            else:
                # If all chunks are silent, return original
                return audio
                
        except Exception as e:
            logger.warning(f"Basic noise reduction failed, using original audio: {str(e)}")
            return audio
    
    def get_audio_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get audio file information without processing
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            Dictionary with audio metadata
        """
        try:
            input_path = Path(file_path)
            if not input_path.exists():
                raise FileNotFoundError(f"Audio file not found: {file_path}")
            
            audio = AudioSegment.from_file(str(input_path))
            file_size_mb = input_path.stat().st_size / (1024 * 1024)
            
            return {
                "title": input_path.stem,
                "duration_seconds": len(audio) / 1000.0,
                "file_size_mb": file_size_mb,
                "format": input_path.suffix.lower().lstrip('.'),
                "sample_rate": audio.frame_rate,
                "channels": audio.channels,
                "frame_rate": audio.frame_rate,
                "sample_width": audio.sample_width,
                "max_amplitude": audio.max_possible_amplitude
            }
            
        except Exception as e:
            logger.error(f"Failed to get audio info: {str(e)}")
            raise Exception(f"Failed to get audio info: {str(e)}")
    
    def validate_audio_file(self, file_path: str) -> bool:
        """
        Validate audio file
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            True if valid, False otherwise
        """
        try:
            input_path = Path(file_path)
            if not input_path.exists():
                return False
            
            # Try to load audio
            audio = AudioSegment.from_file(str(input_path))
            
            # Check if audio has content
            return len(audio) > 0
            
        except Exception:
            return False
    
    def split_audio_if_needed(self, audio_path: str, job_id: str, max_chunk_size_mb: float = 9.0) -> list:
        """
        Split audio file into chunks if it exceeds size limit for STT
        
        Args:
            audio_path: Path to the audio file
            job_id: Job identifier
            max_chunk_size_mb: Maximum chunk size in MB
            
        Returns:
            List of chunk file paths
        """
        try:
            input_path = Path(audio_path)
            file_size_mb = input_path.stat().st_size / (1024 * 1024)
            
            if file_size_mb <= max_chunk_size_mb:
                return [audio_path]
            
            logger.info(f"Splitting audio file ({file_size_mb:.2f} MB) into chunks for job {job_id}")
            
            audio = AudioSegment.from_file(str(input_path))
            
            # Calculate optimal chunk duration based on target size
            # For 45-minute videos (~48MB), we want chunks that are ~9MB each
            total_duration_ms = len(audio)
            estimated_total_size_mb = self._estimate_wav_size(audio)
            
            # Calculate how many chunks we need
            num_chunks = max(1, int(estimated_total_size_mb / max_chunk_size_mb) + 1)
            chunk_duration_ms = total_duration_ms // num_chunks
            
            # Ensure minimum chunk duration (30 seconds) for quality
            min_chunk_duration_ms = 30 * 1000
            chunk_duration_ms = max(chunk_duration_ms, min_chunk_duration_ms)
            
            logger.info(f"Creating {num_chunks} chunks of ~{chunk_duration_ms/1000:.1f}s each for job {job_id}")
            
            chunks = []
            
            for i, chunk_start in enumerate(range(0, len(audio), chunk_duration_ms)):
                chunk_end = min(chunk_start + chunk_duration_ms, len(audio))
                chunk = audio[chunk_start:chunk_end]
                
                # Process each chunk for STT optimization
                processed_chunk = self._process_for_stt(chunk, f"{job_id}_chunk_{i}", max_chunk_size_mb)
                
                chunk_filename = f"{job_id}_chunk_{i:03d}.wav"
                chunk_path = self.output_path / chunk_filename
                
                processed_chunk.export(str(chunk_path), format="wav")
                
                # Verify chunk size
                chunk_size_mb = chunk_path.stat().st_size / (1024 * 1024)
                logger.info(f"Chunk {i}: {chunk_size_mb:.2f}MB, duration: {len(processed_chunk)/1000:.1f}s")
                
                chunks.append(str(chunk_path))
            
            logger.info(f"Audio split into {len(chunks)} optimized chunks for job {job_id}")
            return chunks
            
        except Exception as e:
            logger.error(f"Audio splitting failed for job {job_id}: {str(e)}")
            raise Exception(f"Audio splitting failed: {str(e)}") 