from pydantic import BaseModel
from pydantic_settings import BaseSettings
from typing import Optional
import os


class GoogleCloudConfig(BaseModel):
    """Google Cloud configuration"""
    credentials_path: Optional[str] = None
    project_id: Optional[str] = None
    bucket_name: Optional[str] = None


class STTConfig(BaseModel):
    """Speech-to-Text configuration"""
    language_code: str = "cmn-Hans-CN"
    model: str = "video"
    enable_word_time_offsets: bool = True
    enable_automatic_punctuation: bool = True
    cost_limit_usd: float = 10.0


class SubtitleConfig(BaseModel):
    """Subtitle configuration"""
    max_line_length: int = 42
    max_lines: int = 2


class StorageConfig(BaseModel):
    """Storage configuration"""
    type: str = "local"  # local or gcs
    local_path: str = "./data/processed"
    max_file_size_mb: int = 500
    max_processing_time_seconds: int = 3600


class APIConfig(BaseModel):
    """API configuration"""
    host: str = "0.0.0.0"
    port: int = 8000
    key: Optional[str] = None


class Settings(BaseSettings):
    """Application settings"""
    
    # App info
    app_name: str = "sermon-workflow"
    app_version: str = "1.0.0"
    debug: bool = True
    log_level: str = "INFO"
    
    # Google Cloud
    google_application_credentials: Optional[str] = None
    google_cloud_project: Optional[str] = None
    gcs_bucket_name: Optional[str] = None
    
    # Storage
    storage_type: str = "local"
    local_storage_path: str = "./data/processed"
    max_file_size_mb: int = 500
    max_processing_time_seconds: int = 3600
    
    # Speech-to-Text
    stt_language_code: str = "cmn-Hans-CN"
    stt_model: str = "video"
    stt_enable_word_time_offsets: bool = True
    stt_enable_automatic_punctuation: bool = True
    stt_cost_limit_usd: float = 10.0
    
    # Subtitles
    subtitle_max_line_length: int = 42
    subtitle_max_lines: int = 2
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_password: Optional[str] = None
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: Optional[str] = None
    
    # Database
    database_url: str = "sqlite:///./sermon_workflow.db"
    
    # Development
    reload: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @property
    def google_cloud(self) -> GoogleCloudConfig:
        return GoogleCloudConfig(
            credentials_path=self.google_application_credentials,
            project_id=self.google_cloud_project,
            bucket_name=self.gcs_bucket_name
        )
    
    @property
    def stt(self) -> STTConfig:
        return STTConfig(
            language_code=self.stt_language_code,
            model=self.stt_model,
            enable_word_time_offsets=self.stt_enable_word_time_offsets,
            enable_automatic_punctuation=self.stt_enable_automatic_punctuation,
            cost_limit_usd=self.stt_cost_limit_usd
        )
    
    @property
    def subtitle(self) -> SubtitleConfig:
        return SubtitleConfig(
            max_line_length=self.subtitle_max_line_length,
            max_lines=self.subtitle_max_lines
        )
    
    @property
    def storage(self) -> StorageConfig:
        return StorageConfig(
            type=self.storage_type,
            local_path=self.local_storage_path,
            max_file_size_mb=self.max_file_size_mb,
            max_processing_time_seconds=self.max_processing_time_seconds
        )
    
    @property
    def api(self) -> APIConfig:
        return APIConfig(
            host=self.api_host,
            port=self.api_port,
            key=self.api_key
        )


# Global settings instance
settings = Settings() 