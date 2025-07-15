import logging
from typing import Tuple, Dict, Any, List
from pathlib import Path
from pydub import AudioSegment
from pydub.utils import which
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
            logger.debug(f"Starting audio extraction for job {job_id}: {file_path}")
            
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
            
            # Save processed audio as 16-bit WAV for Google STT compatibility
            output_filename = f"{job_id}_processed.wav"
            output_path = self.output_path / output_filename
            logger.info(f"Saving as 16-bit WAV for Google STT for job {job_id}")
            
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
    
    def _process_for_stt(self, audio: AudioSegment, job_id: str, target_size_mb: float = 8.0) -> AudioSegment:
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
            logger.debug(f"Processing audio for STT optimization (target: {target_size_mb}MB) for job {job_id}")
            
            # Convert to mono if stereo
            if audio.channels > 1:
                logger.debug(f"Converting stereo to mono for job {job_id}")
                audio = audio.set_channels(1)
            
            # Preserve original sample rate for STT (Google supports 8kHz-48kHz, but we enforce 16kHz minimum)
            # Only resample if outside supported range or if very low quality
            if audio.frame_rate < 16000:
                target_sample_rate = 16000
                logger.debug(f"Upsampling from {audio.frame_rate}Hz to {target_sample_rate}Hz for better STT quality for job {job_id}")
                audio = audio.set_frame_rate(target_sample_rate)
            elif audio.frame_rate > 48000:
                target_sample_rate = 48000
                logger.debug(f"Downsampling from {audio.frame_rate}Hz to {target_sample_rate}Hz (Google STT limit) for job {job_id}")
                audio = audio.set_frame_rate(target_sample_rate)
            else:
                logger.debug(f"Preserving original sample rate {audio.frame_rate}Hz for job {job_id}")
            
            # Normalize audio levels first to maximize dynamic range
            audio = audio.normalize()
            logger.debug(f"Normalized audio levels for job {job_id}")
            
            # Convert to 16-bit for Google STT WAV compatibility
            # Google STT requires 16-bit samples for LINEAR_PCM (WAV)
            if audio.sample_width != 2:
                logger.debug(f"Converting from {audio.sample_width * 8}-bit to 16-bit for Google STT for job {job_id}")
                logger.debug(f"Before conversion: sample_width={audio.sample_width}, max_possible_amplitude={audio.max_possible_amplitude}")
                audio = audio.set_sample_width(2)  # 16-bit
                logger.debug(f"After conversion: sample_width={audio.sample_width}, max_possible_amplitude={audio.max_possible_amplitude}")
            else:
                logger.debug(f"Audio already 16-bit for Google STT for job {job_id}")
            
            # Apply noise reduction if available (basic implementation)
            audio = self._apply_basic_noise_reduction(audio)
            
            # Check if we need further compression
            estimated_size_mb = self._estimate_wav_size(audio)
            logger.debug(f"Estimated WAV size: {estimated_size_mb:.2f}MB for job {job_id}")
            
            if estimated_size_mb > target_size_mb:
                logger.debug(f"Audio too large ({estimated_size_mb:.2f}MB), applying compression for job {job_id}")
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
                # Aggressive compression needed - use alternative compression methods instead of reducing sample rate below 16kHz
                if audio.frame_rate > 16000:
                    # Only reduce sample rate if currently above 16kHz
                    new_sample_rate = max(16000, int(audio.frame_rate * 0.5))
                    logger.info(f"Reducing sample rate to {new_sample_rate}Hz for job {job_id} (minimum 16kHz enforced)")
                    audio = audio.set_frame_rate(new_sample_rate)
                else:
                    logger.info(f"Cannot reduce sample rate below 16kHz for job {job_id}, using alternative compression")
                
                # Apply more aggressive dynamic range compression instead of reducing sample rate
                logger.info(f"Applying aggressive dynamic range compression for job {job_id}")
                audio = audio.compress_dynamic_range(threshold=-25.0, ratio=8.0, attack=2.0, release=20.0)
                
            elif compression_ratio < 0.8:
                # Moderate compression - slight sample rate reduction but maintain minimum 16kHz
                if audio.frame_rate > 16000:
                    new_sample_rate = max(16000, int(audio.frame_rate * 0.75))
                    logger.info(f"Reducing sample rate to {new_sample_rate}Hz for job {job_id} (minimum 16kHz enforced)")
                    audio = audio.set_frame_rate(new_sample_rate)
                else:
                    logger.info(f"Sample rate already at minimum 16kHz for job {job_id}, skipping reduction")
            
            # Apply standard dynamic range compression to reduce file size (if not already applied aggressively)
            if compression_ratio >= 0.5:
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
        Apply basic noise reduction while preserving original timing
        
        Args:
            audio: Input audio segment
            
        Returns:
            Processed audio with reduced noise but original duration
        """
        try:
            # For now, disable aggressive noise reduction that removes silent parts
            # This was causing the audio to be shortened significantly
            # TODO: Implement proper noise reduction that attenuates but doesn't remove silence
            
            logger.info("Skipping aggressive noise reduction to preserve audio duration")
            return audio
            
            # Future implementation could use proper noise reduction like:
            # - Spectral subtraction
            # - Wiener filtering
            # - Libraries like noisereduce
            # But should preserve the original timing structure
                
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
    
    def split_audio_if_needed(self, audio_path: str, job_id: str, max_chunk_size_mb: float = 8.0) -> list:
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
            
            # Calculate how many chunks we need - be more conservative
            # Use 1.5x safety margin to account for processing variations
            safety_margin = 1.5
            num_chunks = max(1, int((estimated_total_size_mb * safety_margin) / max_chunk_size_mb) + 1)
            chunk_duration_ms = total_duration_ms // num_chunks
            
            # Ensure minimum chunk duration (30 seconds) for quality
            # But also ensure maximum chunk duration (60 seconds) for Google STT inline limit
            min_chunk_duration_ms = 30 * 1000
            max_chunk_duration_ms = 60 * 1000  # Google STT inline audio limit
            
            chunk_duration_ms = max(chunk_duration_ms, min_chunk_duration_ms)
            chunk_duration_ms = min(chunk_duration_ms, max_chunk_duration_ms)
            
            # If chunks would be too long, increase number of chunks
            if chunk_duration_ms >= max_chunk_duration_ms:
                # Recalculate to ensure chunks are under 60 seconds
                num_chunks = max(num_chunks, int(total_duration_ms / max_chunk_duration_ms) + 1)
                chunk_duration_ms = total_duration_ms // num_chunks
                chunk_duration_ms = max(chunk_duration_ms, min_chunk_duration_ms)
            
            logger.info(f"Creating {num_chunks} chunks of ~{chunk_duration_ms/1000:.1f}s each for job {job_id}")
            
            chunks = []
            
            for i, chunk_start in enumerate(range(0, len(audio), chunk_duration_ms)):
                chunk_end = min(chunk_start + chunk_duration_ms, len(audio))
                chunk = audio[chunk_start:chunk_end]
                
                # Skip empty chunks (can happen at audio boundaries)
                if len(chunk) == 0:
                    logger.warning(f"Skipping empty chunk {i} for job {job_id}")
                    continue
                
                # Process each chunk for STT optimization
                processed_chunk = self._process_for_stt(chunk, f"{job_id}_chunk_{i}", max_chunk_size_mb)
                
                # Validate processed chunk before saving
                if len(processed_chunk) == 0:
                    logger.warning(f"Skipping chunk {i} - became empty after processing for job {job_id}")
                    continue
                
                # Ensure minimum chunk duration (5 seconds) after processing
                min_processed_duration_ms = 5 * 1000
                if len(processed_chunk) < min_processed_duration_ms:
                    logger.warning(f"Skipping chunk {i} - too short ({len(processed_chunk)/1000:.1f}s) after processing for job {job_id}")
                    continue
                
                # Check estimated size before export - Google has 10MB limit
                estimated_chunk_size_mb = self._estimate_wav_size(processed_chunk)
                google_limit_mb = 10.0  # Google Cloud STT limit
                
                if estimated_chunk_size_mb > google_limit_mb:
                    logger.warning(f"Chunk {i} too large ({estimated_chunk_size_mb:.2f}MB > {google_limit_mb}MB), applying additional compression for job {job_id}")
                    # Apply more aggressive compression
                    processed_chunk = self._compress_audio(processed_chunk, f"{job_id}_chunk_{i}", google_limit_mb * 0.9)
                    
                    # Re-check size after compression
                    estimated_chunk_size_mb = self._estimate_wav_size(processed_chunk)
                    if estimated_chunk_size_mb > google_limit_mb:
                        logger.error(f"Chunk {i} still too large ({estimated_chunk_size_mb:.2f}MB) after compression, splitting further for job {job_id}")
                        # Split this chunk further
                        sub_chunks = self._split_oversized_chunk(processed_chunk, f"{job_id}_chunk_{i}", google_limit_mb * 0.9)
                        
                        # Export sub-chunks
                        for sub_i, sub_chunk in enumerate(sub_chunks):
                            sub_chunk_filename = f"{job_id}_chunk_{i:03d}_{sub_i:03d}.wav"
                            sub_chunk_path = self.output_path / sub_chunk_filename
                            sub_chunk.export(str(sub_chunk_path), format="wav")
                            
                            sub_chunk_size_mb = sub_chunk_path.stat().st_size / (1024 * 1024)
                            logger.info(f"Sub-chunk {i}-{sub_i}: {sub_chunk_size_mb:.2f}MB, duration: {len(sub_chunk)/1000:.1f}s")
                            chunks.append(str(sub_chunk_path))
                        continue
                
                chunk_filename = f"{job_id}_chunk_{i:03d}.wav"
                chunk_path = self.output_path / chunk_filename
                
                processed_chunk.export(str(chunk_path), format="wav")
                
                # Verify chunk size after export
                chunk_size_mb = chunk_path.stat().st_size / (1024 * 1024)
                chunk_duration_s = len(processed_chunk) / 1000
                
                # Final validation - remove invalid chunks
                if chunk_size_mb <= 0.001 or chunk_duration_s <= 0.1:
                    logger.warning(f"Removing invalid chunk {i} (size: {chunk_size_mb:.3f}MB, duration: {chunk_duration_s:.1f}s) for job {job_id}")
                    chunk_path.unlink(missing_ok=True)
                    continue
                
                # Final Google limit check
                if chunk_size_mb > google_limit_mb:
                    logger.error(f"Chunk {i} exceeds Google limit: {chunk_size_mb:.2f}MB > {google_limit_mb}MB for job {job_id}")
                    chunk_path.unlink(missing_ok=True)
                    continue
                
                logger.info(f"Chunk {i}: {chunk_size_mb:.2f}MB, duration: {chunk_duration_s:.1f}s")
                chunks.append(str(chunk_path))
            
            # Ensure we have at least one valid chunk
            if not chunks:
                logger.error(f"No valid chunks created for job {job_id} - falling back to original file")
                return [audio_path]
            
            logger.info(f"Audio split into {len(chunks)} optimized chunks for job {job_id}")
            return chunks
            
        except Exception as e:
            logger.error(f"Audio splitting failed for job {job_id}: {str(e)}")
            raise Exception(f"Audio splitting failed: {str(e)}")
    
    def _split_oversized_chunk(self, audio: AudioSegment, chunk_id: str, target_size_mb: float) -> List[AudioSegment]:
        """Split a chunk that's too large into smaller sub-chunks"""
        try:
            current_size_mb = self._estimate_wav_size(audio)
            duration_ms = len(audio)
            
            # Calculate how many sub-chunks we need
            num_sub_chunks = max(2, int(current_size_mb / target_size_mb) + 1)
            sub_chunk_duration_ms = duration_ms // num_sub_chunks
            
            # Ensure minimum sub-chunk duration
            min_sub_chunk_duration_ms = 10 * 1000  # 10 seconds minimum
            sub_chunk_duration_ms = max(sub_chunk_duration_ms, min_sub_chunk_duration_ms)
            
            logger.info(f"Splitting oversized chunk {chunk_id} ({current_size_mb:.2f}MB) into {num_sub_chunks} sub-chunks")
            
            sub_chunks = []
            for i in range(0, len(audio), sub_chunk_duration_ms):
                end_pos = min(i + sub_chunk_duration_ms, len(audio))
                sub_chunk = audio[i:end_pos]
                
                if len(sub_chunk) >= min_sub_chunk_duration_ms:
                    sub_chunks.append(sub_chunk)
                else:
                    logger.warning(f"Skipping very short sub-chunk ({len(sub_chunk)/1000:.1f}s) for {chunk_id}")
            
            return sub_chunks
            
        except Exception as e:
            logger.error(f"Failed to split oversized chunk {chunk_id}: {str(e)}")
            # Return original chunk as fallback
            return [audio] 