import os
import logging
import ssl
import certifi
import yt_dlp
import json
from typing import Optional, Tuple
from pathlib import Path
from pydub import AudioSegment
from app.config import settings

# Fix SSL certificate issues on macOS
ssl._create_default_https_context = ssl._create_unverified_context

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
            logger.debug(f"Starting YouTube download for job {job_id}: {url}")
            
            # Configure yt-dlp options
            output_filename = f"{job_id}_audio.%(ext)s"
            output_path_template = str(self.download_path / output_filename)
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': output_path_template,
                'extractaudio': True,
                'audioformat': 'mp3',
                'quiet': True,
                'no_warnings': True,
            }
            
            # Get video info first
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Get video metadata
                metadata = {
                    "title": info.get('title', ''),
                    "description": info.get('description', ''),
                    "author": info.get('uploader', ''),
                    "length": info.get('duration', 0),
                    "views": info.get('view_count', 0),
                    "publish_date": info.get('upload_date', ''),
                    "thumbnail_url": info.get('thumbnail', '')
                }
                
                # Validate duration (max 2 hours for STT batch limit)
                duration = info.get('duration', 0)
                if duration > 7200:  # 2 hours in seconds
                    raise ValueError(f"Video duration ({duration}s) exceeds maximum allowed (7200s)")
                
                logger.info(f"Video metadata - Title: {info.get('title', '')}, Duration: {duration}s")
            
            # Download audio
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Find the downloaded file
            downloaded_files = list(self.download_path.glob(f"{job_id}_audio.*"))
            if not downloaded_files:
                raise ValueError("Downloaded file not found")
            
            output_path = downloaded_files[0]
            
            # Verify file exists and has content
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise ValueError("Downloaded file is empty or doesn't exist")
            
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"Download completed: {output_path} ({file_size_mb:.2f} MB)")
            
            # Update metadata with file info
            metadata.update({
                "file_size_mb": file_size_mb,
                "audio_format": output_path.suffix[1:],  # Remove the dot
                "audio_bitrate": "best available"
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
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    "title": info.get('title', ''),
                    "description": info.get('description', ''),
                    "author": info.get('uploader', ''),
                    "length": info.get('duration', 0),
                    "views": info.get('view_count', 0),
                    "publish_date": info.get('upload_date', ''),
                    "thumbnail_url": info.get('thumbnail', ''),
                    "available_qualities": [f.get('height', 'unknown') for f in info.get('formats', []) if f.get('vcodec') != 'none'],
                    "available_audio_bitrates": [f.get('abr', 'unknown') for f in info.get('formats', []) if f.get('acodec') != 'none']
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
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                return info.get('title') is not None
        except Exception:
            return False 