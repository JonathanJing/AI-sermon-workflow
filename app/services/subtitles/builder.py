import os
import logging
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import pysubs2
from pysubs2 import SSAFile, SSAEvent
from app.config import settings
from app.models import TranscriptResult, TranscriptEntry, SubtitleEntry

logger = logging.getLogger(__name__)


class SubtitleBuilder:
    """Service for building subtitle files from transcripts"""
    
    def __init__(self):
        self.config = settings.subtitle
        self.output_path = Path(settings.storage.local_path) / "processed"
        self.output_path.mkdir(parents=True, exist_ok=True)
    
    def create_subtitles(self, transcript_result: TranscriptResult, job_id: str) -> Tuple[str, str, Dict[str, Any]]:
        """
        Create subtitle files from transcript
        
        Args:
            transcript_result: Transcript result from STT
            job_id: Unique job identifier
            
        Returns:
            Tuple of (srt_path, vtt_path, metadata)
            
        Raises:
            Exception: If subtitle creation fails
        """
        try:
            logger.info(f"Starting subtitle creation for job {job_id}")
            
            # Process transcript entries into subtitle entries
            subtitle_entries = self._process_transcript_entries(transcript_result.entries, job_id)
            
            # Create subtitle file object
            subtitle_file = self._create_subtitle_file(subtitle_entries, job_id)
            
            # Generate file paths
            srt_filename = f"{job_id}_subtitles.srt"
            vtt_filename = f"{job_id}_subtitles.vtt"
            srt_path = self.output_path / srt_filename
            vtt_path = self.output_path / vtt_filename
            
            # Save SRT file
            subtitle_file.save(str(srt_path), format_="srt")
            
            # Save VTT file
            subtitle_file.save(str(vtt_path), format_="vtt")
            
            # Generate metadata
            metadata = {
                "total_entries": len(subtitle_entries),
                "total_duration": transcript_result.total_duration,
                "language": transcript_result.language,
                "max_line_length": self.config.max_line_length,
                "max_lines": self.config.max_lines,
                "srt_file_size": srt_path.stat().st_size,
                "vtt_file_size": vtt_path.stat().st_size,
                "average_entry_duration": sum(entry.end_time - entry.start_time for entry in subtitle_entries) / len(subtitle_entries) if subtitle_entries else 0
            }
            
            logger.info(f"Subtitle creation completed for job {job_id}: {len(subtitle_entries)} entries")
            
            return str(srt_path), str(vtt_path), metadata
            
        except Exception as e:
            logger.error(f"Subtitle creation failed for job {job_id}: {str(e)}")
            raise Exception(f"Subtitle creation failed: {str(e)}")
    
    def _process_transcript_entries(self, transcript_entries: List[TranscriptEntry], job_id: str) -> List[SubtitleEntry]:
        """Process transcript entries into properly formatted subtitle entries"""
        try:
            subtitle_entries = []
            
            for i, entry in enumerate(transcript_entries):
                # Clean and format text
                cleaned_text = self._clean_text(entry.text)
                
                # Split text into lines if too long
                lines = self._split_text_into_lines(cleaned_text)
                
                # Create subtitle entry
                subtitle_entry = SubtitleEntry(
                    start_time=entry.start_time,
                    end_time=entry.end_time,
                    text='\n'.join(lines),
                    position=i + 1
                )
                
                subtitle_entries.append(subtitle_entry)
            
            # Post-process to ensure proper timing and avoid overlaps
            subtitle_entries = self._post_process_timing(subtitle_entries)
            
            return subtitle_entries
            
        except Exception as e:
            logger.error(f"Failed to process transcript entries for job {job_id}: {str(e)}")
            raise Exception(f"Failed to process transcript entries: {str(e)}")
    
    def _clean_text(self, text: str) -> str:
        """Clean and format text for subtitles"""
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Fix common punctuation issues
        text = text.replace(' ,', ',')
        text = text.replace(' .', '.')
        text = text.replace(' !', '!')
        text = text.replace(' ?', '?')
        text = text.replace(' ;', ';')
        text = text.replace(' :', ':')
        
        # Handle Chinese punctuation
        text = text.replace(' ，', '，')
        text = text.replace(' 。', '。')
        text = text.replace(' ！', '！')
        text = text.replace(' ？', '？')
        text = text.replace(' ；', '；')
        text = text.replace(' ：', '：')
        
        return text.strip()
    
    def _split_text_into_lines(self, text: str) -> List[str]:
        """Split text into lines based on configuration"""
        if len(text) <= self.config.max_line_length:
            return [text]
        
        # Split by words
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            word_length = len(word)
            
            # Check if adding this word would exceed line length
            if current_length + word_length + len(current_line) > self.config.max_line_length:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                    current_length = word_length
                else:
                    # Word itself is too long, split it
                    lines.append(word[:self.config.max_line_length])
                    current_line = []
                    current_length = 0
            else:
                current_line.append(word)
                current_length += word_length
        
        # Add remaining words
        if current_line:
            lines.append(' '.join(current_line))
        
        # Limit to max lines
        if len(lines) > self.config.max_lines:
            lines = lines[:self.config.max_lines]
            # Add ellipsis to indicate truncation
            if lines:
                lines[-1] += '...'
        
        return lines
    
    def _post_process_timing(self, subtitle_entries: List[SubtitleEntry]) -> List[SubtitleEntry]:
        """Post-process subtitle entries to fix timing issues"""
        processed_entries = []
        
        for i, entry in enumerate(subtitle_entries):
            # Ensure minimum display duration (1 second)
            min_duration = 1.0
            if entry.end_time - entry.start_time < min_duration:
                entry.end_time = entry.start_time + min_duration
            
            # Ensure maximum display duration (6 seconds)
            max_duration = 6.0
            if entry.end_time - entry.start_time > max_duration:
                entry.end_time = entry.start_time + max_duration
            
            # Avoid overlaps with next entry
            if i < len(subtitle_entries) - 1:
                next_entry = subtitle_entries[i + 1]
                if entry.end_time > next_entry.start_time:
                    # Leave 0.1 second gap
                    entry.end_time = next_entry.start_time - 0.1
            
            processed_entries.append(entry)
        
        return processed_entries
    
    def _create_subtitle_file(self, subtitle_entries: List[SubtitleEntry], job_id: str) -> SSAFile:
        """Create pysubs2 subtitle file object"""
        try:
            subtitle_file = SSAFile()
            
            for entry in subtitle_entries:
                # Convert time to milliseconds
                start_ms = int(entry.start_time * 1000)
                end_ms = int(entry.end_time * 1000)
                
                # Create SSA event
                event = SSAEvent(
                    start=start_ms,
                    end=end_ms,
                    text=entry.text
                )
                
                subtitle_file.append(event)
            
            return subtitle_file
            
        except Exception as e:
            logger.error(f"Failed to create subtitle file for job {job_id}: {str(e)}")
            raise Exception(f"Failed to create subtitle file: {str(e)}")
    
    def validate_subtitle_file(self, file_path: str) -> bool:
        """Validate subtitle file"""
        try:
            subtitle_file = pysubs2.load(file_path)
            return len(subtitle_file) > 0
            
        except Exception:
            return False
    
    def get_subtitle_info(self, file_path: str) -> Dict[str, Any]:
        """Get subtitle file information"""
        try:
            subtitle_file = pysubs2.load(file_path)
            
            if not subtitle_file:
                raise ValueError("Empty subtitle file")
            
            # Calculate statistics
            total_duration = (subtitle_file[-1].end - subtitle_file[0].start) / 1000.0
            average_duration = sum(event.end - event.start for event in subtitle_file) / len(subtitle_file) / 1000.0
            
            return {
                "total_entries": len(subtitle_file),
                "total_duration": total_duration,
                "average_entry_duration": average_duration,
                "first_entry_start": subtitle_file[0].start / 1000.0,
                "last_entry_end": subtitle_file[-1].end / 1000.0,
                "format": Path(file_path).suffix.lower().lstrip('.'),
                "file_size": Path(file_path).stat().st_size
            }
            
        except Exception as e:
            logger.error(f"Failed to get subtitle info: {str(e)}")
            raise Exception(f"Failed to get subtitle info: {str(e)}")
    
    def convert_subtitle_format(self, input_path: str, output_path: str, target_format: str) -> str:
        """Convert subtitle file to different format"""
        try:
            logger.info(f"Converting subtitle from {input_path} to {output_path} ({target_format})")
            
            # Load subtitle file
            subtitle_file = pysubs2.load(input_path)
            
            # Save in target format
            subtitle_file.save(output_path, format_=target_format)
            
            logger.info(f"Subtitle conversion completed: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Subtitle conversion failed: {str(e)}")
            raise Exception(f"Subtitle conversion failed: {str(e)}")
    
    def merge_subtitles(self, subtitle_paths: List[str], output_path: str) -> str:
        """Merge multiple subtitle files into one"""
        try:
            logger.info(f"Merging {len(subtitle_paths)} subtitle files")
            
            merged_file = SSAFile()
            current_offset = 0
            
            for path in subtitle_paths:
                subtitle_file = pysubs2.load(path)
                
                for event in subtitle_file:
                    # Adjust timing based on offset
                    new_event = SSAEvent(
                        start=event.start + current_offset,
                        end=event.end + current_offset,
                        text=event.text
                    )
                    merged_file.append(new_event)
                
                # Update offset for next file
                if subtitle_file:
                    current_offset = subtitle_file[-1].end + 1000  # 1 second gap
            
            # Save merged file
            merged_file.save(output_path)
            
            logger.info(f"Subtitle merge completed: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Subtitle merge failed: {str(e)}")
            raise Exception(f"Subtitle merge failed: {str(e)}")
    
    def extract_text_only(self, subtitle_path: str) -> str:
        """Extract only text content from subtitle file"""
        try:
            subtitle_file = pysubs2.load(subtitle_path)
            
            text_content = []
            for event in subtitle_file:
                # Clean subtitle-specific formatting
                clean_text = event.plaintext
                if clean_text.strip():
                    text_content.append(clean_text.strip())
            
            return '\n'.join(text_content)
            
        except Exception as e:
            logger.error(f"Failed to extract text: {str(e)}")
            raise Exception(f"Failed to extract text: {str(e)}") 