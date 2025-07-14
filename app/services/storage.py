import os
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import json
import shutil
from app.config import settings

logger = logging.getLogger(__name__)


class StorageService(ABC):
    """Abstract base class for storage services"""
    
    @abstractmethod
    def save_file(self, file_path: str, destination_key: str) -> str:
        """Save file to storage"""
        pass
    
    @abstractmethod
    def get_file_url(self, file_key: str, expires_in: int = 3600) -> str:
        """Get downloadable URL for file"""
        pass
    
    @abstractmethod
    def delete_file(self, file_key: str) -> bool:
        """Delete file from storage"""
        pass
    
    @abstractmethod
    def list_files(self, prefix: str = "") -> List[Dict[str, Any]]:
        """List files in storage"""
        pass
    
    @abstractmethod
    def file_exists(self, file_key: str) -> bool:
        """Check if file exists in storage"""
        pass


class LocalStorageService(StorageService):
    """Local file system storage implementation"""
    
    def __init__(self):
        self.storage_path = Path(settings.storage.local_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Local storage initialized at {self.storage_path}")
    
    def save_file(self, file_path: str, destination_key: str) -> str:
        """Save file to local storage"""
        try:
            source_path = Path(file_path)
            if not source_path.exists():
                raise FileNotFoundError(f"Source file not found: {file_path}")
            
            # Create destination path
            destination_path = self.storage_path / destination_key
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(source_path, destination_path)
            
            logger.info(f"File saved to local storage: {destination_path}")
            return destination_key
            
        except Exception as e:
            logger.error(f"Failed to save file to local storage: {str(e)}")
            raise Exception(f"Failed to save file: {str(e)}")
    
    def get_file_url(self, file_key: str, expires_in: int = 3600) -> str:
        """Get file URL for local storage (file path)"""
        try:
            file_path = self.storage_path / file_key
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_key}")
            
            # For local storage, return file path
            # In production, this would be served via web server
            return f"/files/{file_key}"
            
        except Exception as e:
            logger.error(f"Failed to get file URL: {str(e)}")
            raise Exception(f"Failed to get file URL: {str(e)}")
    
    def delete_file(self, file_key: str) -> bool:
        """Delete file from local storage"""
        try:
            file_path = self.storage_path / file_key
            if file_path.exists():
                file_path.unlink()
                logger.info(f"File deleted from local storage: {file_key}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete file: {str(e)}")
            return False
    
    def list_files(self, prefix: str = "") -> List[Dict[str, Any]]:
        """List files in local storage"""
        try:
            files = []
            search_path = self.storage_path
            
            if prefix:
                search_path = search_path / prefix
            
            if search_path.exists():
                for file_path in search_path.rglob("*"):
                    if file_path.is_file():
                        relative_path = file_path.relative_to(self.storage_path)
                        stat = file_path.stat()
                        
                        files.append({
                            "key": str(relative_path),
                            "size": stat.st_size,
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            "etag": f'"{stat.st_mtime}_{stat.st_size}"'
                        })
            
            return files
            
        except Exception as e:
            logger.error(f"Failed to list files: {str(e)}")
            return []
    
    def file_exists(self, file_key: str) -> bool:
        """Check if file exists in local storage"""
        try:
            file_path = self.storage_path / file_key
            return file_path.exists()
            
        except Exception:
            return False


class GoogleCloudStorageService(StorageService):
    """Google Cloud Storage implementation"""
    
    def __init__(self):
        self.client = None
        self.bucket_name = settings.google_cloud.bucket_name
        self.bucket = None
        
        # Initialize client if credentials are available
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Google Cloud Storage client"""
        try:
            if not self.bucket_name:
                raise ValueError("GCS bucket name not configured")
            
            # Import here to avoid dependency if not using GCS
            from google.cloud import storage
            
            if settings.google_cloud.credentials_path:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_cloud.credentials_path
            
            self.client = storage.Client()
            self.bucket = self.client.bucket(self.bucket_name)
            
            logger.info(f"Google Cloud Storage initialized: {self.bucket_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Cloud Storage: {str(e)}")
            self.client = None
            self.bucket = None
    
    def save_file(self, file_path: str, destination_key: str) -> str:
        """Save file to Google Cloud Storage"""
        if not self.client or not self.bucket:
            raise Exception("Google Cloud Storage client not initialized")
        
        try:
            source_path = Path(file_path)
            if not source_path.exists():
                raise FileNotFoundError(f"Source file not found: {file_path}")
            
            # Create blob and upload
            blob = self.bucket.blob(destination_key)
            blob.upload_from_filename(str(source_path))
            
            logger.info(f"File uploaded to GCS: gs://{self.bucket_name}/{destination_key}")
            return destination_key
            
        except Exception as e:
            logger.error(f"Failed to save file to GCS: {str(e)}")
            raise Exception(f"Failed to save file: {str(e)}")
    
    def get_file_url(self, file_key: str, expires_in: int = 3600) -> str:
        """Get signed URL for Google Cloud Storage file"""
        if not self.client or not self.bucket:
            raise Exception("Google Cloud Storage client not initialized")
        
        try:
            blob = self.bucket.blob(file_key)
            
            if not blob.exists():
                raise FileNotFoundError(f"File not found: {file_key}")
            
            # Generate signed URL
            url = blob.generate_signed_url(
                version="v4",
                expiration=datetime.utcnow() + timedelta(seconds=expires_in),
                method="GET"
            )
            
            return url
            
        except Exception as e:
            logger.error(f"Failed to get file URL: {str(e)}")
            raise Exception(f"Failed to get file URL: {str(e)}")
    
    def delete_file(self, file_key: str) -> bool:
        """Delete file from Google Cloud Storage"""
        if not self.client or not self.bucket:
            return False
        
        try:
            blob = self.bucket.blob(file_key)
            if blob.exists():
                blob.delete()
                logger.info(f"File deleted from GCS: {file_key}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete file: {str(e)}")
            return False
    
    def list_files(self, prefix: str = "") -> List[Dict[str, Any]]:
        """List files in Google Cloud Storage"""
        if not self.client or not self.bucket:
            return []
        
        try:
            blobs = self.bucket.list_blobs(prefix=prefix)
            files = []
            
            for blob in blobs:
                files.append({
                    "key": blob.name,
                    "size": blob.size,
                    "modified": blob.time_created.isoformat(),
                    "etag": blob.etag
                })
            
            return files
            
        except Exception as e:
            logger.error(f"Failed to list files: {str(e)}")
            return []
    
    def file_exists(self, file_key: str) -> bool:
        """Check if file exists in Google Cloud Storage"""
        if not self.client or not self.bucket:
            return False
        
        try:
            blob = self.bucket.blob(file_key)
            return blob.exists()
            
        except Exception:
            return False


class StorageManager:
    """Storage manager that handles both local and cloud storage"""
    
    def __init__(self):
        self.storage_type = settings.storage.type
        
        if self.storage_type == "gcs":
            self.storage_service = GoogleCloudStorageService()
        else:
            self.storage_service = LocalStorageService()
        
        logger.info(f"Storage manager initialized with {self.storage_type} storage")
    
    def save_job_files(self, job_id: str, files: Dict[str, str]) -> Dict[str, str]:
        """
        Save all files for a job to storage
        
        Args:
            job_id: Job identifier
            files: Dictionary of file_type -> file_path
            
        Returns:
            Dictionary of file_type -> storage_key
        """
        try:
            saved_files = {}
            
            for file_type, file_path in files.items():
                if file_path and Path(file_path).exists():
                    # Generate storage key
                    filename = Path(file_path).name
                    storage_key = f"jobs/{job_id}/{file_type}/{filename}"
                    
                    # Save to storage
                    self.storage_service.save_file(file_path, storage_key)
                    saved_files[file_type] = storage_key
            
            logger.info(f"Saved {len(saved_files)} files for job {job_id}")
            return saved_files
            
        except Exception as e:
            logger.error(f"Failed to save job files: {str(e)}")
            raise Exception(f"Failed to save job files: {str(e)}")
    
    def get_job_file_urls(self, job_id: str, file_keys: Dict[str, str], expires_in: int = 3600) -> Dict[str, str]:
        """
        Get download URLs for job files
        
        Args:
            job_id: Job identifier
            file_keys: Dictionary of file_type -> storage_key
            expires_in: URL expiration time in seconds
            
        Returns:
            Dictionary of file_type -> download_url
        """
        try:
            download_urls = {}
            
            for file_type, storage_key in file_keys.items():
                if storage_key:
                    try:
                        url = self.storage_service.get_file_url(storage_key, expires_in)
                        download_urls[file_type] = url
                    except Exception as e:
                        logger.warning(f"Failed to get URL for {file_type}: {str(e)}")
            
            return download_urls
            
        except Exception as e:
            logger.error(f"Failed to get job file URLs: {str(e)}")
            return {}
    
    def cleanup_job_files(self, job_id: str, file_keys: Dict[str, str]) -> Dict[str, bool]:
        """
        Clean up job files from storage
        
        Args:
            job_id: Job identifier
            file_keys: Dictionary of file_type -> storage_key
            
        Returns:
            Dictionary of file_type -> deletion_success
        """
        try:
            cleanup_results = {}
            
            for file_type, storage_key in file_keys.items():
                if storage_key:
                    success = self.storage_service.delete_file(storage_key)
                    cleanup_results[file_type] = success
            
            logger.info(f"Cleaned up files for job {job_id}")
            return cleanup_results
            
        except Exception as e:
            logger.error(f"Failed to cleanup job files: {str(e)}")
            return {}
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        try:
            files = self.storage_service.list_files()
            
            if not files:
                return {"total_files": 0, "total_size": 0, "storage_type": self.storage_type}
            
            total_size = sum(f.get("size", 0) for f in files)
            
            return {
                "total_files": len(files),
                "total_size": total_size,
                "storage_type": self.storage_type,
                "recent_files": sorted(files, key=lambda x: x.get("modified", ""), reverse=True)[:10]
            }
            
        except Exception as e:
            logger.error(f"Failed to get storage stats: {str(e)}")
            return {"error": str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """Check storage service health"""
        try:
            # Try to list files as a health check
            files = self.storage_service.list_files()
            
            return {
                "status": "healthy",
                "storage_type": self.storage_type,
                "accessible": True,
                "file_count": len(files) if files else 0
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "storage_type": self.storage_type,
                "accessible": False,
                "error": str(e)
            }


# Global storage manager instance
storage_manager = StorageManager() 