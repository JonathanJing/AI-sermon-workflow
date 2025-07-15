import os
import logging
import json
from typing import List, Dict, Any, Tuple
from pathlib import Path
from google.cloud import speech_v2 as speech
from google.api_core import exceptions as gcp_exceptions
# Optional GCS import - only needed for long audio files
try:
    from google.cloud import storage
    GCS_AVAILABLE = True
except ImportError:
    storage = None
    GCS_AVAILABLE = False
from app.config import settings
from app.models import TranscriptEntry, TranscriptResult
from app.services.phrase_manager import PhraseManager
from app.services.subtitles.builder import SubtitleBuilder

logger = logging.getLogger(__name__)


class GoogleSTTService:
    """Service for Google Cloud Speech-to-Text transcription"""
    
    def __init__(self):
        self.client = None
        self.config = settings.stt
        self.output_path = Path(settings.storage.local_path) / "processed"
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize phrase manager
        self.phrase_manager = PhraseManager()
        
        # Initialize subtitle builder
        self.subtitle_builder = SubtitleBuilder()
        
        # Initialize storage client for GCS uploads
        self.storage_client = None
        
        # Initialize recognizer name for v2 API
        self.recognizer_name = None
        
        # Initialize client if credentials are available
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Google Cloud Speech client"""
        try:
            if settings.google_cloud.credentials_path:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_cloud.credentials_path
            
            self.client = speech.SpeechClient()
            logger.debug("Google Cloud Speech client initialized successfully")
            
            # Initialize storage client for GCS uploads
            if GCS_AVAILABLE and settings.google_cloud.bucket_name:
                self.storage_client = storage.Client()
                logger.debug("Google Cloud Storage client initialized successfully")
            else:
                if not GCS_AVAILABLE:
                    logger.warning("Google Cloud Storage not available - long audio files (>60s) will fail. Install with: pip install google-cloud-storage")
                elif not settings.google_cloud.bucket_name:
                    logger.warning("GCS bucket name not configured - long audio files may fail")
                self.storage_client = None
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Cloud clients: {str(e)}")
            self.client = None
            self.storage_client = None
    
    def _get_or_create_recognizer(self) -> str:
        """Get or create a recognizer for v2 API"""
        if self.recognizer_name:
            return self.recognizer_name
        
        try:
            # Create recognizer name
            project_id = settings.google_cloud.project_id
            recognizer_id = "default-recognizer"
            location = "global"
            
            self.recognizer_name = f"projects/{project_id}/locations/{location}/recognizers/{recognizer_id}"
            
            # Try to get existing recognizer
            try:
                self.client.get_recognizer(name=self.recognizer_name)
                logger.debug(f"Using existing recognizer: {self.recognizer_name}")
                return self.recognizer_name
            except gcp_exceptions.NotFound:
                # Create new recognizer
                logger.debug(f"Creating new recognizer: {self.recognizer_name}")
                
                # Create default recognition config for the recognizer
                default_config = self._create_recognition_config(16000)
                
                recognizer = speech.Recognizer(
                    default_recognition_config=default_config
                )
                
                request = speech.CreateRecognizerRequest(
                    parent=f"projects/{project_id}/locations/{location}",
                    recognizer_id=recognizer_id,
                    recognizer=recognizer
                )
                
                operation = self.client.create_recognizer(request=request)
                # Wait for the operation to complete
                operation.result()
                
                logger.debug(f"Created recognizer: {self.recognizer_name}")
                return self.recognizer_name
                
        except Exception as e:
            logger.error(f"Failed to get or create recognizer: {str(e)}")
            raise Exception(f"Failed to get or create recognizer: {str(e)}")
    
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
                logger.debug(f"Processing {len(chunk_files)} audio chunks for job {job_id}")
                return self._transcribe_chunked_audio(chunk_files, job_id)
            else:
                logger.debug(f"Processing single audio file for job {job_id}")
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
                # Sort by chunk number, handling both chunk_001.wav and chunk_001_000.wav patterns
                def sort_key(file_path):
                    stem = file_path.stem
                    parts = stem.split('_')
                    if len(parts) >= 3:
                        try:
                            # Handle chunk_001_000.wav pattern (sub-chunks)
                            if len(parts) >= 4 and parts[-2].isdigit() and parts[-1].isdigit():
                                return (int(parts[-2]), int(parts[-1]))
                            # Handle chunk_001.wav pattern (regular chunks)
                            elif parts[-1].isdigit():
                                return (int(parts[-1]), 0)
                        except ValueError:
                            pass
                    return (0, 0)
                
                chunk_files.sort(key=sort_key)
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
            
            # Initialize incremental SRT file
            srt_path = None
            vtt_path = None
            
            logger.info(f"Transcribing {len(chunk_files)} chunks for job {job_id}")
            
            for i, chunk_file in enumerate(chunk_files):
                logger.debug(f"Processing chunk {i+1}/{len(chunk_files)}: {chunk_file}")
                
                try:
                    # Validate chunk file before processing
                    chunk_path = Path(chunk_file)
                    if not chunk_path.exists():
                        logger.error(f"Chunk file does not exist: {chunk_file}")
                        continue
                    
                    # Check file size
                    chunk_size_mb = chunk_path.stat().st_size / (1024 * 1024)
                    if chunk_size_mb <= 0.001:  # Less than 1KB
                        logger.warning(f"Skipping tiny chunk {i+1} (size: {chunk_size_mb:.3f}MB): {chunk_file}")
                        continue
                    
                    # Check audio duration
                    try:
                        from pydub import AudioSegment
                        audio_segment = AudioSegment.from_wav(chunk_file)
                        chunk_duration_seconds = len(audio_segment) / 1000.0
                        
                        if chunk_duration_seconds <= 0.1:  # Less than 100ms
                            logger.warning(f"Skipping very short chunk {i+1} (duration: {chunk_duration_seconds:.1f}s): {chunk_file}")
                            continue
                            
                    except Exception as e:
                        logger.warning(f"Could not validate chunk {i+1} audio properties: {str(e)}")
                        # Continue processing anyway
                    
                    chunk_result, chunk_metadata = self._transcribe_single_file(chunk_file, f"{job_id}_chunk_{i}")
                    
                    # Skip chunks with no transcription results
                    if not chunk_result.entries:
                        logger.warning(f"Chunk {i+1} produced no transcription results: {chunk_file}")
                        continue
                    
                    # Adjust timing for chunk offset
                    chunk_offset = total_duration
                    adjusted_entries = []
                    for entry in chunk_result.entries:
                        # Create a copy with adjusted timing
                        adjusted_entry = TranscriptEntry(
                            start_time=entry.start_time + chunk_offset,
                            end_time=entry.end_time + chunk_offset,
                            text=entry.text,
                            confidence=entry.confidence
                        )
                        adjusted_entries.append(adjusted_entry)
                        all_entries.append(adjusted_entry)
                    
                    # Append to incremental SRT file
                    try:
                        srt_path = self.subtitle_builder.append_chunk_to_srt(adjusted_entries, job_id, srt_path)
                        logger.debug(f"Appended chunk {i+1} to SRT file: {srt_path}")
                    except Exception as e:
                        logger.warning(f"Failed to append chunk {i+1} to SRT file: {str(e)}")
                        # Continue processing even if SRT append fails
                    
                    # Update totals
                    total_duration += chunk_result.total_duration
                    total_cost += chunk_metadata.get("estimated_cost_usd", 0.0)
                    processing_methods.append(chunk_metadata.get("transcription_method", "unknown"))
                    
                    if chunk_result.confidence:
                        total_confidence += chunk_result.confidence
                        confidence_count += 1
                    
                    logger.info(f"Successfully processed chunk {i+1}: {len(chunk_result.entries)} entries, duration: {chunk_result.total_duration:.1f}s")
                    
                except Exception as e:
                    logger.error(f"Failed to process chunk {i+1} for job {job_id}: {str(e)}")
                    # Continue with other chunks
                    continue
            
            if not all_entries:
                logger.error(f"No chunks were successfully transcribed for job {job_id}. Total chunks attempted: {len(chunk_files)}")
                raise Exception(f"No chunks were successfully transcribed out of {len(chunk_files)} chunks")
            
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
            
            # Generate VTT file from the incremental SRT file if it exists
            if srt_path and Path(srt_path).exists():
                try:
                    # Generate VTT file from the existing SRT
                    vtt_path = self._convert_srt_to_vtt(srt_path, job_id)
                    logger.info(f"Subtitle files available: {srt_path}, {vtt_path}")
                except Exception as e:
                    logger.warning(f"Failed to create VTT file from SRT for job {job_id}: {str(e)}")
                    vtt_path = None
            else:
                # Fallback to creating subtitle files from complete transcript
                logger.info("No incremental SRT file available, creating subtitle files from complete transcript")
                try:
                    srt_path, vtt_path, subtitle_metadata = self.subtitle_builder.create_subtitles(transcript_result, job_id)
                    logger.info(f"Subtitle files created: {srt_path}, {vtt_path}")
                except Exception as e:
                    logger.warning(f"Failed to create subtitle files for job {job_id}: {str(e)}")
                    # Continue without subtitles if creation fails
            
            # Create processing metadata
            processing_metadata = {
                "transcription_method": "chunked",
                "chunks_processed": len(chunk_files),
                "chunks_successful": len([e for e in all_entries if e]),
                "file_size_mb": sum(Path(f).stat().st_size for f in chunk_files) / (1024 * 1024),
                "transcript_path": transcript_path,
                "srt_path": srt_path,
                "vtt_path": vtt_path,
                "estimated_cost_usd": total_cost,
                "confidence_score": overall_confidence,
                "language_detected": self.config.language_code,
                "total_alternatives": len(all_entries),
                "processing_methods": list(set(processing_methods))
            }
            
            confidence_str = f"{overall_confidence:.3f}" if overall_confidence else "N/A"
            logger.info(f"Chunked transcription completed for job {job_id}: {len(all_entries)} entries, "
                       f"confidence: {confidence_str}")
            
            return transcript_result, processing_metadata
            
        except Exception as e:
            logger.error(f"Chunked transcription failed for job {job_id}: {str(e)}")
            
            # Try to preserve partial results if we have any
            if all_entries:
                logger.warning(f"Preserving partial results for job {job_id}: {len(all_entries)} entries processed")
                
                # Calculate overall confidence for partial results
                overall_confidence = total_confidence / confidence_count if confidence_count > 0 else None
                
                # Create partial transcript result
                partial_transcript = TranscriptResult(
                    entries=all_entries,
                    total_duration=total_duration,
                    language=self.config.language_code,
                    confidence=overall_confidence
                )
                
                # Try to save partial transcript
                try:
                    transcript_path = self._save_transcript(partial_transcript, f"{job_id}_partial")
                    logger.info(f"Partial transcript saved: {transcript_path}")
                except Exception as save_error:
                    logger.error(f"Failed to save partial transcript: {str(save_error)}")
                    transcript_path = None
                
                # Create partial processing metadata
                partial_metadata = {
                    "transcription_method": "chunked_partial",
                    "chunks_attempted": len(chunk_files),
                    "chunks_successful": len(all_entries),
                    "transcript_path": transcript_path,
                    "srt_path": srt_path,
                    "vtt_path": vtt_path,
                    "estimated_cost_usd": total_cost,
                    "confidence_score": overall_confidence,
                    "language_detected": self.config.language_code,
                    "total_alternatives": len(all_entries),
                    "processing_methods": list(set(processing_methods)),
                    "partial_result": True,
                    "failure_reason": str(e)
                }
                
                logger.warning(f"Returning partial results for job {job_id}: {len(all_entries)} entries")
                return partial_transcript, partial_metadata
            
            raise Exception(f"Chunked transcription failed: {str(e)}")
    
    def _convert_srt_to_vtt(self, srt_path: str, job_id: str) -> str:
        """Convert SRT file to VTT format"""
        try:
            import pysubs2
            
            # Load SRT file
            subs = pysubs2.load(srt_path)
            
            # Generate VTT file path
            vtt_path = srt_path.replace("_subtitles.srt", "_subtitles.vtt")
            
            # Save as VTT
            subs.save(vtt_path, format_="vtt")
            
            logger.info(f"Converted SRT to VTT for job {job_id}: {vtt_path}")
            return vtt_path
            
        except Exception as e:
            logger.error(f"Failed to convert SRT to VTT for job {job_id}: {str(e)}")
            raise Exception(f"Failed to convert SRT to VTT: {str(e)}")
    
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
                logger.debug(f"Detected sample rate: {detected_sample_rate}Hz for {job_id}")
                logger.debug(f"Audio duration: {audio_duration_seconds:.1f}s for {job_id}")
            except Exception as e:
                logger.warning(f"Could not detect audio properties for {job_id}, using defaults: {str(e)}")
                detected_sample_rate = 16000
                audio_duration_seconds = 0  # If we can't detect duration, assume it's short
            
            # Determine transcription method based on Google STT limits
            # Synchronous API: < 60 seconds and < 10MB
            # Long-running API with inline audio: < 60 seconds but > 10MB
            # Long-running API with GCS URI: > 60 seconds (duration limit for inline audio)
            
            use_gcs = audio_duration_seconds > 60  # Google's inline audio duration limit
            use_long_running = audio_duration_seconds > 60 or file_size_mb > 10
            
            # Create recognition config with detected sample rate
            config = self._create_recognition_config(sample_rate=detected_sample_rate)
            
            if use_gcs:
                # Upload to GCS and use URI for long audio files
                if not GCS_AVAILABLE:
                    raise Exception("Long audio file (>60s) requires Google Cloud Storage. Install with: pip install google-cloud-storage")
                
                if not self.storage_client or not settings.google_cloud.bucket_name:
                    raise Exception("GCS not configured but required for long audio files (>60s). Set GCS_BUCKET_NAME environment variable.")
                
                logger.info(f"Uploading to GCS for long audio file {job_id} (duration: {audio_duration_seconds:.1f}s)")
                gcs_uri = self._upload_to_gcs(audio_file_path, job_id)
                
                # Use batch operation with GCS URI
                logger.info(f"Using batch operation with GCS URI for {job_id}")
                response = self._transcribe_batch(config, gcs_uri, job_id)
                
                # Clean up GCS file after transcription
                self._cleanup_gcs_file(gcs_uri)
                
            else:
                # Use inline audio for shorter files
                with open(audio_file_path, 'rb') as audio_file:
                    content = audio_file.read()
                
                # Perform transcription
                if use_long_running:
                    # For longer files, upload to GCS and use batch operation
                    logger.info(f"Using batch operation for {job_id} (duration: {audio_duration_seconds:.1f}s, file size: {file_size_mb:.2f} MB)")
                    gcs_uri = self._upload_to_gcs(audio_file_path, job_id)
                    response = self._transcribe_batch(config, gcs_uri, job_id)
                    self._cleanup_gcs_file(gcs_uri)
                else:
                    logger.info(f"Using synchronous operation for {job_id} (duration: {audio_duration_seconds:.1f}s, file size: {file_size_mb:.2f} MB)")
                    response = self._transcribe_synchronous(config, content, job_id)
            
            # Process results
            transcript_result = self._process_transcription_results(response, job_id)
            
            # Save transcript JSON
            transcript_path = self._save_transcript(transcript_result, job_id)
            
            # Generate subtitle files
            srt_path = None
            vtt_path = None
            try:
                srt_path, vtt_path, subtitle_metadata = self.subtitle_builder.create_subtitles(transcript_result, job_id)
                logger.info(f"Subtitle files created: {srt_path}, {vtt_path}")
            except Exception as e:
                logger.warning(f"Failed to create subtitle files for job {job_id}: {str(e)}")
                # Continue without subtitles if creation fails
            
            # Calculate processing metadata
            processing_metadata = {
                "transcription_method": "long_running" if use_long_running else "synchronous",
                "file_size_mb": file_size_mb,
                "audio_duration_seconds": audio_duration_seconds,
                "transcript_path": transcript_path,
                "srt_path": srt_path,
                "vtt_path": vtt_path,
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
        
        # Validate model compatibility with Chinese language and v2 API
        if self.config.language_code.startswith("cmn-") and self.config.model == "video":
            logger.warning(f"Video model is not supported for Chinese language {self.config.language_code}. Using 'latest_long' model instead.")
            model_to_use = "latest_long"
        elif self.config.model == "default":
            # Map v1 "default" model to v2 "latest_long" model
            model_to_use = "latest_long"
        else:
            model_to_use = self.config.model
            
        logger.info(f"  - final model to use: {model_to_use}")
        
        # Configure recognition features
        features = speech.RecognitionFeatures(
            enable_word_time_offsets=self.config.enable_word_time_offsets,
            enable_automatic_punctuation=self.config.enable_automatic_punctuation,
            enable_word_confidence=True,
            profanity_filter=False,
            # Speaker diarization is configured via diarization_config
            # Currently disabled as it may not be fully supported in v2
            # diarization_config=speech.SpeakerDiarizationConfig(
            #     min_speaker_count=1,
            #     max_speaker_count=2  # Typical for sermons (pastor + maybe reader)
            # )
        )
        
        # Configure speech adaptation context
        # Note: Phrase adaptation in v2 API has a different structure
        # For now, we'll skip phrase adaptation and add it later when we have the correct structure
        adaptation = None
        
        config = speech.RecognitionConfig(
            auto_decoding_config=speech.AutoDetectDecodingConfig(),
            language_codes=[self.config.language_code],
            model=model_to_use,  # Use validated model
            features=features
        )
        
        # Add adaptation if available
        if adaptation:
            config.adaptation = adaptation
        
        # Debug: Print the final config
        logger.info(f"Final recognition config: {config}")
        
        return config
    
    def _transcribe_synchronous(self, config: speech.RecognitionConfig, audio_content: bytes, job_id: str) -> speech.RecognizeResponse:
        """Perform synchronous transcription"""
        try:
            recognizer = self._get_or_create_recognizer()
            
            request = speech.RecognizeRequest(
                recognizer=recognizer,
                config=config,
                content=audio_content
            )
            response = self.client.recognize(request=request)
            return response
            
        except gcp_exceptions.GoogleAPICallError as e:
            logger.error(f"Google API error for job {job_id}: {str(e)}")
            raise Exception(f"Google API error: {str(e)}")
    
    def _transcribe_batch(self, config: speech.RecognitionConfig, audio_uri: str, job_id: str) -> speech.BatchRecognizeResponse:
        """Perform batch transcription for long audio files"""
        try:
            recognizer = self._get_or_create_recognizer()
            
            # Create batch file metadata
            file_metadata = speech.BatchRecognizeFileMetadata(
                uri=audio_uri,
                config=config
            )
            
            request = speech.BatchRecognizeRequest(
                recognizer=recognizer,
                config=config,
                files=[file_metadata]
            )
            
            operation = self.client.batch_recognize(request=request)
            
            logger.info(f"Batch operation started for job {job_id}: {operation.name}")
            
            # Wait for completion with timeout
            response = operation.result(timeout=settings.storage.max_processing_time_seconds)
            return response
            
        except gcp_exceptions.GoogleAPICallError as e:
            logger.error(f"Google API error for job {job_id}: {str(e)}")
            raise Exception(f"Google API error: {str(e)}")
        except Exception as e:
            logger.error(f"Batch operation failed for job {job_id}: {str(e)}")
            raise Exception(f"Batch operation failed: {str(e)}")
    
    def _upload_to_gcs(self, audio_file_path: str, job_id: str) -> str:
        """Upload audio file to Google Cloud Storage and return URI"""
        try:
            if not GCS_AVAILABLE:
                raise Exception("Google Cloud Storage not available")
            
            if not self.storage_client or not settings.google_cloud.bucket_name:
                raise Exception("GCS client or bucket not configured")
            
            # Create unique blob name
            audio_filename = Path(audio_file_path).name
            blob_name = f"stt-temp/{job_id}/{audio_filename}"
            
            # Get bucket and create blob
            bucket = self.storage_client.bucket(settings.google_cloud.bucket_name)
            blob = bucket.blob(blob_name)
            
            # Upload file
            logger.info(f"Uploading {audio_file_path} to gs://{settings.google_cloud.bucket_name}/{blob_name}")
            blob.upload_from_filename(audio_file_path)
            
            # Return GCS URI
            gcs_uri = f"gs://{settings.google_cloud.bucket_name}/{blob_name}"
            logger.info(f"Upload completed: {gcs_uri}")
            
            return gcs_uri
            
        except Exception as e:
            logger.error(f"Failed to upload to GCS for job {job_id}: {str(e)}")
            raise Exception(f"GCS upload failed: {str(e)}")
    
    def _cleanup_gcs_file(self, gcs_uri: str):
        """Clean up temporary GCS file"""
        try:
            if not GCS_AVAILABLE or not self.storage_client or not gcs_uri.startswith("gs://"):
                return
            
            # Parse GCS URI
            parts = gcs_uri.replace("gs://", "").split("/", 1)
            bucket_name = parts[0]
            blob_name = parts[1]
            
            # Delete blob
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.delete()
            
            logger.info(f"Cleaned up GCS file: {gcs_uri}")
            
        except Exception as e:
            logger.warning(f"Failed to cleanup GCS file {gcs_uri}: {str(e)}")
            # Don't raise exception for cleanup failures
    
    def _process_transcription_results(self, response, job_id: str) -> TranscriptResult:
        """Process transcription results into structured format"""
        try:
            entries = []
            total_confidence = 0
            confidence_count = 0
            
            # Handle different response types for v2 API
            if hasattr(response, 'results') and response.results:
                # Synchronous response
                results_list = response.results
            elif hasattr(response, 'results') and hasattr(response.results, 'results'):
                # Batch response - extract results from the first (and typically only) file
                if response.results:
                    first_result = list(response.results.values())[0]
                    if hasattr(first_result, 'transcript') and first_result.transcript:
                        results_list = first_result.transcript.results
                    else:
                        results_list = []
                else:
                    results_list = []
            else:
                results_list = []
            
            for result in results_list:
                # Check if there are alternatives
                if not result.alternatives:
                    logger.warning(f"No alternatives found in result for job {job_id}")
                    continue
                    
                # Get the best alternative
                alternative = result.alternatives[0]
                
                # Extract words with timing
                if hasattr(alternative, 'words') and alternative.words:
                    # Segment words into meaningful phrases using multiple strategies
                    entries.extend(self._segment_words_into_phrases(alternative.words, alternative.confidence))
                    
                    # Update confidence tracking
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
                "entries": [entry.model_dump() for entry in transcript_result.entries],
                "total_duration": transcript_result.total_duration,
                "language": transcript_result.language,
                "confidence": transcript_result.confidence,
                "generated_at": str(transcript_result.entries[0].start_time) if transcript_result.entries else None
            }
            
            with open(transcript_path, 'w', encoding='utf-8') as f:
                json.dump(transcript_dict, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Transcript saved to {transcript_path}")
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
    
    def _segment_words_into_phrases(self, words, confidence):
        """
        Segment words into meaningful phrases using multiple strategies:
        1. Time-based segmentation (natural pauses)
        2. Length-based segmentation (every N words)
        3. Punctuation-based segmentation
        """
        entries = []
        current_phrase = []
        current_start = None
        
        max_phrase_length = 15  # Maximum words per phrase
        min_pause_duration = 0.8  # Minimum pause to consider phrase boundary (seconds)
        
        for i, word in enumerate(words):
            # Start new phrase if needed
            if current_start is None:
                current_start = self._get_word_start_time(word)
            
            current_phrase.append(word.word)
            
            # Check for phrase boundary conditions
            should_end_phrase = False
            
            # 1. Punctuation-based boundary
            if word.word.endswith(('.', '!', '?', '。', '！', '？', '，', ',')):
                should_end_phrase = True
            
            # 2. Time-based boundary (significant pause after this word)
            elif i < len(words) - 1:
                next_word = words[i + 1]
                word_end_time = self._get_word_end_time(word)
                next_word_start_time = self._get_word_start_time(next_word)
                pause_duration = next_word_start_time - word_end_time
                if pause_duration >= min_pause_duration:
                    should_end_phrase = True
            
            # 3. Length-based boundary (max words reached)
            if len(current_phrase) >= max_phrase_length:
                should_end_phrase = True
            
            # 4. End of words
            if i == len(words) - 1:
                should_end_phrase = True
            
            # Create phrase entry if boundary detected
            if should_end_phrase and current_phrase:
                entry = TranscriptEntry(
                    start_time=current_start,
                    end_time=self._get_word_end_time(word),
                    text=' '.join(current_phrase),
                    confidence=confidence
                )
                entries.append(entry)
                
                # Reset for next phrase
                current_phrase = []
                current_start = None
        return entries
    
    def _parse_time_offset(self, time_offset_str: str) -> float:
        """
        Parse time offset string from Google STT v2 API to float seconds.
        
        Args:
            time_offset_str: Time offset string like "0s", "1.100s", "2.300s"
            
        Returns:
            Time in seconds as float
        """
        if not time_offset_str:
            return 0.0
        
        try:
            # Remove 's' suffix and convert to float
            if time_offset_str.endswith('s'):
                return float(time_offset_str[:-1])
            else:
                return float(time_offset_str)
        except (ValueError, AttributeError):
            logger.warning(f"Failed to parse time offset: {time_offset_str}")
            return 0.0
    
    def _get_word_start_time(self, word) -> float:
        """
        Get start time from word object, handling both v1 and v2 API formats.
        
        Args:
            word: WordInfo object from Google STT API
            
        Returns:
            Start time in seconds as float
        """
        # v2 API uses start_offset as string
        if hasattr(word, 'start_offset') and word.start_offset:
            return self._parse_time_offset(word.start_offset)
        # v1 API uses start_time as duration object
        elif hasattr(word, 'start_time') and word.start_time:
            if hasattr(word.start_time, 'total_seconds'):
                return word.start_time.total_seconds()
            else:
                return self._parse_time_offset(str(word.start_time))
        else:
            return 0.0
    
    def _get_word_end_time(self, word) -> float:
        """
        Get end time from word object, handling both v1 and v2 API formats.
        
        Args:
            word: WordInfo object from Google STT API
            
        Returns:
            End time in seconds as float
        """
        # v2 API uses end_offset as string
        if hasattr(word, 'end_offset') and word.end_offset:
            return self._parse_time_offset(word.end_offset)
        # v1 API uses end_time as duration object
        elif hasattr(word, 'end_time') and word.end_time:
            if hasattr(word.end_time, 'total_seconds'):
                return word.end_time.total_seconds()
            else:
                return self._parse_time_offset(str(word.end_time))
        else:
            return 0.0
    
    def health_check(self) -> Dict[str, Any]:
        """Check service health"""
        try:
            if not self.client:
                return {"status": "unhealthy", "error": "Client not initialized"}
            
            return {
                "status": "healthy",
                "client_initialized": True,
                "gcs_available": GCS_AVAILABLE,
                "gcs_configured": bool(self.storage_client and settings.google_cloud.bucket_name),
                "language_code": self.config.language_code,
                "model": self.config.model,
                "cost_limit_usd": self.config.cost_limit_usd
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            } 