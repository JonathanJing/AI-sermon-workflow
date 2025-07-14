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
    
    def _process_for_stt(self, audio: AudioSegment, job_id: str) -> AudioSegment:
        """
        Process audio for optimal STT performance
        
        Args:
            audio: Input audio segment
            job_id: Job identifier for logging
            
        Returns:
            Processed audio segment
        """
        try:
            # Convert to mono if stereo
            if audio.channels > 1:
                logger.info(f"Converting stereo to mono for job {job_id}")
                audio = audio.set_channels(1)
            
            # Optimal sample rate for Google STT is 16kHz or 48kHz
            # Use 16kHz for better cost/performance ratio
            target_sample_rate = 16000
            if audio.frame_rate != target_sample_rate:
                logger.info(f"Resampling from {audio.frame_rate}Hz to {target_sample_rate}Hz for job {job_id}")
                audio = audio.set_frame_rate(target_sample_rate)
            
            # Normalize audio levels
            audio = audio.normalize()
            
            # Apply noise reduction if available (basic implementation)
            audio = self._apply_basic_noise_reduction(audio)
            
            return audio
            
        except Exception as e:
            logger.error(f"Audio processing failed for job {job_id}: {str(e)}")
            raise Exception(f"Audio processing failed: {str(e)}")
    
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
    
    def split_audio_if_needed(self, audio_path: str, job_id: str, max_chunk_size_mb: int = 10) -> list:
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
            
            # Calculate chunk duration (approximately 1 minute chunks)
            chunk_duration_ms = 60 * 1000  # 1 minute in milliseconds
            chunks = []
            
            for i, chunk_start in enumerate(range(0, len(audio), chunk_duration_ms)):
                chunk_end = min(chunk_start + chunk_duration_ms, len(audio))
                chunk = audio[chunk_start:chunk_end]
                
                chunk_filename = f"{job_id}_chunk_{i:03d}.wav"
                chunk_path = self.output_path / chunk_filename
                
                chunk.export(str(chunk_path), format="wav")
                chunks.append(str(chunk_path))
            
            logger.info(f"Audio split into {len(chunks)} chunks for job {job_id}")
            return chunks
            
        except Exception as e:
            logger.error(f"Audio splitting failed for job {job_id}: {str(e)}")
            raise Exception(f"Audio splitting failed: {str(e)}") 