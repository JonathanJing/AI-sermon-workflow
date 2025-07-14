import os
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from google.cloud import speech_v1p1beta1 as speech
from google.cloud.speech_v1p1beta1 import types
from google.api_core import exceptions as gcp_exceptions
from app.config import settings
from app.models import TranscriptEntry, TranscriptResult

logger = logging.getLogger(__name__)


class GoogleSTTService:
    """Service for Google Cloud Speech-to-Text transcription"""
    
    def __init__(self):
        self.client = None
        self.config = settings.stt
        self.output_path = Path(settings.storage.local_path) / "processed"
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize client if credentials are available
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Google Cloud Speech client"""
        try:
            if settings.google_cloud.credentials_path:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_cloud.credentials_path
            
            self.client = speech.SpeechClient()
            logger.info("Google Cloud Speech client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Cloud Speech client: {str(e)}")
            self.client = None
    
    def transcribe_audio(self, audio_file_path: str, job_id: str) -> Tuple[TranscriptResult, Dict[str, Any]]:
        """
        Transcribe audio file using Google Cloud Speech-to-Text
        Handles both single files and chunked audio files
        
        Args:
            audio_file_path: Path to the audio file or first chunk
            job_id: Unique job identifier
            
        Returns:
            Tuple of (transcript_result, processing_metadata)
            
        Raises:
            Exception: If transcription fails
        """
        if not self.client:
            raise Exception("Google Cloud Speech client not initialized")
        
        try:
            logger.info(f"Starting transcription for job {job_id}: {audio_file_path}")
            
            # Check if this is a chunked audio file
            audio_path = Path(audio_file_path)
            chunk_files = self._find_chunk_files(audio_path, job_id)
            
            if len(chunk_files) > 1:
                logger.info(f"Processing {len(chunk_files)} audio chunks for job {job_id}")
                return self._transcribe_chunked_audio(chunk_files, job_id)
            else:
                logger.info(f"Processing single audio file for job {job_id}")
                return self._transcribe_single_file(audio_file_path, job_id)
            
        except Exception as e:
            logger.error(f"Transcription failed for job {job_id}: {str(e)}")
            raise Exception(f"Transcription failed: {str(e)}")
    
    def _find_chunk_files(self, audio_path: Path, job_id: str) -> List[str]:
        """Find all chunk files for a job"""
        try:
            # Look for chunk files in the same directory
            chunk_pattern = f"{job_id}_chunk_*.wav"
            chunk_files = list(audio_path.parent.glob(chunk_pattern))
            
            if chunk_files:
                # Sort by chunk number
                chunk_files.sort(key=lambda x: int(x.stem.split('_')[-1]))
                return [str(f) for f in chunk_files]
            else:
                # No chunks found, return original file
                return [str(audio_path)]
                
        except Exception as e:
            logger.warning(f"Error finding chunk files for job {job_id}: {str(e)}")
            return [str(audio_path)]
    
    def _transcribe_chunked_audio(self, chunk_files: List[str], job_id: str) -> Tuple[TranscriptResult, Dict[str, Any]]:
        """Transcribe multiple audio chunks and combine results"""
        try:
            all_entries = []
            total_cost = 0.0
            total_confidence = 0.0
            confidence_count = 0
            total_duration = 0.0
            processing_methods = []
            
            logger.info(f"Transcribing {len(chunk_files)} chunks for job {job_id}")
            
            for i, chunk_file in enumerate(chunk_files):
                logger.info(f"Processing chunk {i+1}/{len(chunk_files)}: {chunk_file}")
                
                try:
                    chunk_result, chunk_metadata = self._transcribe_single_file(chunk_file, f"{job_id}_chunk_{i}")
                    
                    # Adjust timing for chunk offset
                    chunk_offset = total_duration
                    for entry in chunk_result.entries:
                        entry.start_time += chunk_offset
                        entry.end_time += chunk_offset
                        all_entries.append(entry)
                    
                    # Update totals
                    total_duration += chunk_result.total_duration
                    total_cost += chunk_metadata.get("estimated_cost_usd", 0.0)
                    processing_methods.append(chunk_metadata.get("transcription_method", "unknown"))
                    
                    if chunk_result.confidence:
                        total_confidence += chunk_result.confidence
                        confidence_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to process chunk {i+1} for job {job_id}: {str(e)}")
                    # Continue with other chunks
                    continue
            
            if not all_entries:
                raise Exception("No chunks were successfully transcribed")
            
            # Calculate overall confidence
            overall_confidence = total_confidence / confidence_count if confidence_count > 0 else None
            
            # Create combined transcript result
            transcript_result = TranscriptResult(
                entries=all_entries,
                total_duration=total_duration,
                language=self.config.language_code,
                confidence=overall_confidence
            )
            
            # Save combined transcript
            transcript_path = self._save_transcript(transcript_result, job_id)
            
            # Create processing metadata
            processing_metadata = {
                "transcription_method": "chunked",
                "chunks_processed": len(chunk_files),
                "chunks_successful": len([e for e in all_entries if e]),
                "file_size_mb": sum(Path(f).stat().st_size for f in chunk_files) / (1024 * 1024),
                "transcript_path": transcript_path,
                "estimated_cost_usd": total_cost,
                "confidence_score": overall_confidence,
                "language_detected": self.config.language_code,
                "total_alternatives": len(all_entries),
                "processing_methods": list(set(processing_methods))
            }
            
            logger.info(f"Chunked transcription completed for job {job_id}: {len(all_entries)} entries, "
                       f"confidence: {overall_confidence:.3f if overall_confidence else 'N/A'}")
            
            return transcript_result, processing_metadata
            
        except Exception as e:
            logger.error(f"Chunked transcription failed for job {job_id}: {str(e)}")
            raise Exception(f"Chunked transcription failed: {str(e)}")
    
    def _transcribe_single_file(self, audio_file_path: str, job_id: str) -> Tuple[TranscriptResult, Dict[str, Any]]:
        """Transcribe a single audio file"""
        try:
            # Load audio file
            audio_path = Path(audio_file_path)
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
            
            # Get file size
            file_size_mb = audio_path.stat().st_size / (1024 * 1024)
            
            # Detect sample rate and duration from the audio file
            try:
                from pydub import AudioSegment
                audio_segment = AudioSegment.from_wav(audio_file_path)
                detected_sample_rate = audio_segment.frame_rate
                audio_duration_seconds = len(audio_segment) / 1000.0  # pydub duration is in milliseconds
                logger.info(f"Detected sample rate: {detected_sample_rate}Hz for {job_id}")
                logger.info(f"Audio duration: {audio_duration_seconds:.1f}s for {job_id}")
            except Exception as e:
                logger.warning(f"Could not detect audio properties for {job_id}, using defaults: {str(e)}")
                detected_sample_rate = 16000
                audio_duration_seconds = 0  # If we can't detect duration, assume it's short
            
            # Determine whether to use long-running operation
            # Google's synchronous API has a 60-second limit for audio duration
            # Also use long-running for very large files (>10MB)
            use_long_running = audio_duration_seconds > 60 or file_size_mb > 10
            
            with open(audio_file_path, 'rb') as audio_file:
                content = audio_file.read()
            
            # Create audio object
            audio = speech.RecognitionAudio(content=content)
            
            # Create recognition config with detected sample rate
            config = self._create_recognition_config(sample_rate=detected_sample_rate)
            
            # Perform transcription
            if use_long_running:
                logger.info(f"Using long-running operation for {job_id} (duration: {audio_duration_seconds:.1f}s, file size: {file_size_mb:.2f} MB)")
                response = self._transcribe_long_running(config, audio, job_id)
            else:
                logger.info(f"Using synchronous operation for {job_id} (duration: {audio_duration_seconds:.1f}s, file size: {file_size_mb:.2f} MB)")
                response = self._transcribe_synchronous(config, audio, job_id)
            
            # Process results
            transcript_result = self._process_transcription_results(response, job_id)
            
            # Calculate processing metadata
            processing_metadata = {
                "transcription_method": "long_running" if use_long_running else "synchronous",
                "file_size_mb": file_size_mb,
                "audio_duration_seconds": audio_duration_seconds,
                "estimated_cost_usd": self._estimate_cost(file_size_mb, transcript_result.total_duration),
                "confidence_score": transcript_result.confidence,
                "language_detected": transcript_result.language,
                "total_alternatives": len(response.results) if response.results else 0
            }
            
            return transcript_result, processing_metadata
            
        except Exception as e:
            logger.error(f"Single file transcription failed for {job_id}: {str(e)}")
            raise Exception(f"Single file transcription failed: {str(e)}")
    
    def _create_recognition_config(self, sample_rate: int = 16000) -> speech.RecognitionConfig:
        """Create recognition configuration"""
        
        # Debug: Print the exact configuration being used
        logger.info(f"Creating recognition config with:")
        logger.info(f"  - language_code: {self.config.language_code}")
        logger.info(f"  - model: {self.config.model}")
        logger.info(f"  - sample_rate_hertz: {sample_rate}")
        logger.info(f"  - enable_word_time_offsets: {self.config.enable_word_time_offsets}")
        logger.info(f"  - enable_automatic_punctuation: {self.config.enable_automatic_punctuation}")
        
        # Validate model compatibility with Chinese language
        if self.config.language_code.startswith("cmn-") and self.config.model == "video":
            logger.warning(f"Video model is not supported for Chinese language {self.config.language_code}. Using 'default' model instead.")
            model_to_use = "default"
        else:
            model_to_use = self.config.model
            
        logger.info(f"  - final model to use: {model_to_use}")
        
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=sample_rate,
            language_code=self.config.language_code,
            model=model_to_use,  # Use validated model
            enable_word_time_offsets=self.config.enable_word_time_offsets,
            enable_automatic_punctuation=self.config.enable_automatic_punctuation,
            use_enhanced=True,  # Use enhanced model for better accuracy
            # Enable speaker diarization if needed
            enable_speaker_diarization=False,  # Can be configurable
            diarization_speaker_count=2,  # Typical for sermons (pastor + maybe reader)
            # Additional features
            enable_word_confidence=True,
            profanity_filter=False,
            speech_contexts=[
                speech.SpeechContext(
                    phrases=["阿门", "哈利路亚", "主耶稣", "神", "圣经", "福音", "祷告", "赞美"]  # Common religious terms
                )
            ]
        )
        
        # Debug: Print the final config
        logger.info(f"Final recognition config: {config}")
        
        return config
    
    def _transcribe_synchronous(self, config: speech.RecognitionConfig, audio: speech.RecognitionAudio, job_id: str) -> speech.RecognizeResponse:
        """Perform synchronous transcription"""
        try:
            request = speech.RecognizeRequest(config=config, audio=audio)
            response = self.client.recognize(request=request)
            return response
            
        except gcp_exceptions.GoogleAPICallError as e:
            logger.error(f"Google API error for job {job_id}: {str(e)}")
            raise Exception(f"Google API error: {str(e)}")
    
    def _transcribe_long_running(self, config: speech.RecognitionConfig, audio: speech.RecognitionAudio, job_id: str) -> speech.RecognizeResponse:
        """Perform long-running transcription"""
        try:
            request = speech.LongRunningRecognizeRequest(config=config, audio=audio)
            operation = self.client.long_running_recognize(request=request)
            
            logger.info(f"Long-running operation started for job {job_id}: {operation.name}")
            
            # Wait for completion with timeout
            response = operation.result(timeout=settings.storage.max_processing_time_seconds)
            return response
            
        except gcp_exceptions.GoogleAPICallError as e:
            logger.error(f"Google API error for job {job_id}: {str(e)}")
            raise Exception(f"Google API error: {str(e)}")
        except Exception as e:
            logger.error(f"Long-running operation failed for job {job_id}: {str(e)}")
            raise Exception(f"Long-running operation failed: {str(e)}")
    
    def _process_transcription_results(self, response: speech.RecognizeResponse, job_id: str) -> TranscriptResult:
        """Process transcription results into structured format"""
        try:
            entries = []
            total_confidence = 0
            confidence_count = 0
            
            for result in response.results:
                # Get the best alternative
                alternative = result.alternatives[0]
                
                # Extract words with timing
                if hasattr(alternative, 'words') and alternative.words:
                    # Group words into sentences or phrases
                    current_sentence = []
                    current_start = None
                    
                    for word in alternative.words:
                        if current_start is None:
                            current_start = word.start_time.total_seconds()
                        
                        current_sentence.append(word.word)
                        
                        # Check if this is end of sentence (basic punctuation detection)
                        if word.word.endswith(('.', '!', '?', '。', '！', '？')):
                            if current_sentence:
                                entry = TranscriptEntry(
                                    start_time=current_start,
                                    end_time=word.end_time.total_seconds(),
                                    text=' '.join(current_sentence),
                                    confidence=alternative.confidence if hasattr(alternative, 'confidence') else None
                                )
                                entries.append(entry)
                                
                                # Update confidence tracking
                                if alternative.confidence:
                                    total_confidence += alternative.confidence
                                    confidence_count += 1
                            
                            current_sentence = []
                            current_start = None
                    
                    # Handle remaining words
                    if current_sentence:
                        last_word = alternative.words[-1]
                        entry = TranscriptEntry(
                            start_time=current_start,
                            end_time=last_word.end_time.total_seconds(),
                            text=' '.join(current_sentence),
                            confidence=alternative.confidence if hasattr(alternative, 'confidence') else None
                        )
                        entries.append(entry)
                        
                        if alternative.confidence:
                            total_confidence += alternative.confidence
                            confidence_count += 1
                else:
                    # Fallback: create single entry without timing
                    entry = TranscriptEntry(
                        start_time=0,
                        end_time=0,
                        text=alternative.transcript,
                        confidence=alternative.confidence if hasattr(alternative, 'confidence') else None
                    )
                    entries.append(entry)
                    
                    if alternative.confidence:
                        total_confidence += alternative.confidence
                        confidence_count += 1
            
            # Calculate overall confidence
            overall_confidence = total_confidence / confidence_count if confidence_count > 0 else None
            
            # Calculate total duration
            total_duration = max([entry.end_time for entry in entries]) if entries else 0
            
            return TranscriptResult(
                entries=entries,
                total_duration=total_duration,
                language=self.config.language_code,
                confidence=overall_confidence
            )
            
        except Exception as e:
            logger.error(f"Failed to process transcription results for job {job_id}: {str(e)}")
            raise Exception(f"Failed to process transcription results: {str(e)}")
    
    def _save_transcript(self, transcript_result: TranscriptResult, job_id: str) -> str:
        """Save transcript to JSON file"""
        try:
            transcript_filename = f"{job_id}_transcript.json"
            transcript_path = self.output_path / transcript_filename
            
            # Convert to dict for JSON serialization
            transcript_dict = {
                "entries": [entry.dict() for entry in transcript_result.entries],
                "total_duration": transcript_result.total_duration,
                "language": transcript_result.language,
                "confidence": transcript_result.confidence,
                "generated_at": str(transcript_result.entries[0].start_time) if transcript_result.entries else None
            }
            
            with open(transcript_path, 'w', encoding='utf-8') as f:
                json.dump(transcript_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Transcript saved to {transcript_path}")
            return str(transcript_path)
            
        except Exception as e:
            logger.error(f"Failed to save transcript for job {job_id}: {str(e)}")
            raise Exception(f"Failed to save transcript: {str(e)}")
    
    def _estimate_cost(self, file_size_mb: float, duration_seconds: float) -> float:
        """Estimate Google Cloud Speech-to-Text cost"""
        try:
            # Google Cloud STT pricing (as of 2024)
            # Standard model: $0.024 per minute
            # Enhanced model: $0.048 per minute
            # Video model: $0.072 per minute
            
            model_rates = {
                "default": 0.024,
                "enhanced": 0.048,
                "video": 0.072,
                "latest_long": 0.048,
                "latest_short": 0.048
            }
            
            rate_per_minute = model_rates.get(self.config.model, 0.048)
            duration_minutes = duration_seconds / 60
            
            estimated_cost = duration_minutes * rate_per_minute
            
            logger.info(f"Estimated STT cost: ${estimated_cost:.4f} for {duration_minutes:.2f} minutes")
            return estimated_cost
            
        except Exception as e:
            logger.error(f"Failed to estimate cost: {str(e)}")
            return 0.0
    
    def check_cost_limit(self, duration_seconds: float) -> bool:
        """Check if transcription would exceed cost limit"""
        try:
            estimated_cost = self._estimate_cost(0, duration_seconds)
            
            if estimated_cost > self.config.cost_limit_usd:
                logger.warning(f"Estimated cost ${estimated_cost:.4f} exceeds limit ${self.config.cost_limit_usd:.4f}")
                return False
            
            return True
            
        except Exception:
            return True  # If we can't estimate, allow the request
    
    def health_check(self) -> Dict[str, Any]:
        """Check service health"""
        try:
            if not self.client:
                return {"status": "unhealthy", "error": "Client not initialized"}
            
            # Try a minimal operation to test connectivity
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=self.config.language_code
            )
            
            return {
                "status": "healthy",
                "client_initialized": True,
                "language_code": self.config.language_code,
                "model": self.config.model,
                "cost_limit_usd": self.config.cost_limit_usd
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            } 