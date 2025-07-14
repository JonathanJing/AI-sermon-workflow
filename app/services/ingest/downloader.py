import os
import logging
from typing import Optional, Tuple
from pathlib import Path
from pytube import YouTube
from pydub import AudioSegment
from app.config import settings

logger = logging.getLogger(__name__)


class YouTubeDownloader:
    """Service for downloading YouTube videos and extracting audio"""
    
    def __init__(self):
        self.download_path = Path(settings.storage.local_path) / "raw"
        self.download_path.mkdir(parents=True, exist_ok=True)
    
    def download_audio(self, url: str, job_id: str) -> Tuple[str, dict]:
        """
        Download audio from YouTube URL
        
        Args:
            url: YouTube video URL
            job_id: Unique job identifier
            
        Returns:
            Tuple of (audio_file_path, metadata)
            
        Raises:
            Exception: If download fails
        """
        try:
            logger.info(f"Starting YouTube download for job {job_id}: {url}")
            
            # Create YouTube object
            yt = YouTube(url)
            
            # Get video metadata
            metadata = {
                "title": yt.title,
                "description": yt.description,
                "author": yt.author,
                "length": yt.length,
                "views": yt.views,
                "publish_date": yt.publish_date.isoformat() if yt.publish_date else None,
                "thumbnail_url": yt.thumbnail_url
            }
            
            # Validate duration (max 2 hours for STT batch limit)
            if yt.length > 7200:  # 2 hours in seconds
                raise ValueError(f"Video duration ({yt.length}s) exceeds maximum allowed (7200s)")
            
            logger.info(f"Video metadata - Title: {yt.title}, Duration: {yt.length}s")
            
            # Get audio stream (prefer high quality)
            audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
            
            if not audio_stream:
                raise ValueError("No audio stream found")
            
            # Download audio
            output_filename = f"{job_id}_audio.{audio_stream.subtype}"
            output_path = self.download_path / output_filename
            
            logger.info(f"Downloading audio stream: {audio_stream.abr} bitrate")
            audio_stream.download(output_path=str(self.download_path), filename=output_filename)
            
            # Verify file exists and has content
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise ValueError("Downloaded file is empty or doesn't exist")
            
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"Download completed: {output_path} ({file_size_mb:.2f} MB)")
            
            # Update metadata with file info
            metadata.update({
                "file_size_mb": file_size_mb,
                "audio_format": audio_stream.subtype,
                "audio_bitrate": audio_stream.abr
            })
            
            return str(output_path), metadata
            
        except Exception as e:
            logger.error(f"YouTube download failed for job {job_id}: {str(e)}")
            raise Exception(f"YouTube download failed: {str(e)}")
    
    def get_video_info(self, url: str) -> dict:
        """
        Get video information without downloading
        
        Args:
            url: YouTube video URL
            
        Returns:
            Dictionary with video metadata
        """
        try:
            yt = YouTube(url)
            return {
                "title": yt.title,
                "description": yt.description,
                "author": yt.author,
                "length": yt.length,
                "views": yt.views,
                "publish_date": yt.publish_date.isoformat() if yt.publish_date else None,
                "thumbnail_url": yt.thumbnail_url,
                "available_qualities": [stream.resolution for stream in yt.streams.filter(file_extension='mp4')],
                "available_audio_bitrates": [stream.abr for stream in yt.streams.filter(only_audio=True)]
            }
        except Exception as e:
            logger.error(f"Failed to get video info: {str(e)}")
            raise Exception(f"Failed to get video info: {str(e)}")
    
    def validate_url(self, url: str) -> bool:
        """
        Validate YouTube URL
        
        Args:
            url: YouTube video URL
            
        Returns:
            True if valid, False otherwise
        """
        try:
            yt = YouTube(url)
            return yt.title is not None
        except Exception:
            return False 