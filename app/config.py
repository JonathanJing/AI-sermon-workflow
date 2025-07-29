"""
应用配置管理
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv
from pathlib import Path

# 加载环境变量
load_dotenv()

class Settings:
    """应用设置类"""
    
    def __init__(self):
        # Google AI配置
        self.GOOGLE_SERVICE_ACCOUNT_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "service-account.json")
        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
        self.GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
        
        # Gemini生成参数
        self.GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", 0.7))
        self.GEMINI_TOP_P = float(os.getenv("GEMINI_TOP_P", 0.8))
        self.GEMINI_TOP_K = int(os.getenv("GEMINI_TOP_K", 40))
        self.GEMINI_MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", 2048))
        
        # 服务配置
        self.HOST = os.getenv("HOST", "0.0.0.0")
        self.PORT = int(os.getenv("PORT", 8000))
        self.DEBUG = os.getenv("DEBUG", "True").lower() == "true"
        
        # 文件路径配置
        self.OUTPUT_DIR = os.getenv("OUTPUT_DIR", "data/clips")
        self.UPLOAD_DIR = os.getenv("UPLOAD_DIR", "data/uploads")
        self.LOG_DIR = os.getenv("LOG_DIR", "logs")
        
        # 视频切片参数
        self.DEFAULT_MIN_DURATION = float(os.getenv("DEFAULT_MIN_DURATION", 10.0))
        self.DEFAULT_MAX_DURATION = float(os.getenv("DEFAULT_MAX_DURATION", 60.0))
        self.DEFAULT_TARGET_COUNT = int(os.getenv("DEFAULT_TARGET_COUNT", 5))
        
        # 质量阈值配置
        self.QUALITY_THRESHOLDS = {
            'min_file_size': int(os.getenv("MIN_FILE_SIZE", 1024)),
            'min_resolution': int(os.getenv("MIN_RESOLUTION", 480)),
            'min_bitrate': int(os.getenv("MIN_BITRATE", 100000)),
            'min_audio_level': float(os.getenv("MIN_AUDIO_LEVEL", -30.0)),
            'content_score': float(os.getenv("CONTENT_SCORE_THRESHOLD", 0.3))
        }
        
        # 安全配置
        self.MAX_FILE_SIZE = os.getenv("MAX_FILE_SIZE", "500MB")
        self.ALLOWED_VIDEO_FORMATS = os.getenv("ALLOWED_VIDEO_FORMATS", "mp4,avi,mov,mkv").split(",")
        self.ALLOWED_SUBTITLE_FORMATS = os.getenv("ALLOWED_SUBTITLE_FORMATS", "srt,vtt").split(",")
        
        # 日志配置
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")
        
        # 创建必要的目录
        self._create_directories()
    
    def _create_directories(self):
        """创建必要的目录"""
        directories = [
            self.OUTPUT_DIR,
            self.UPLOAD_DIR,
            self.LOG_DIR,
            os.path.join(self.OUTPUT_DIR, "uploads"),
            os.path.join(self.OUTPUT_DIR, "results")
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def get_clipping_config(self) -> Dict[str, Any]:
        """获取切片配置"""
        return {
            "service_account_path": self.GOOGLE_SERVICE_ACCOUNT_PATH,
            "google_api_key": self.GOOGLE_API_KEY,
            "model": self.GEMINI_MODEL,
            "output_dir": self.OUTPUT_DIR,
            "quality_thresholds": self.QUALITY_THRESHOLDS,
            "min_duration": self.DEFAULT_MIN_DURATION,
            "max_duration": self.DEFAULT_MAX_DURATION,
            "target_count": self.DEFAULT_TARGET_COUNT,
            "gemini_config": {
                "temperature": self.GEMINI_TEMPERATURE,
                "top_p": self.GEMINI_TOP_P,
                "top_k": self.GEMINI_TOP_K,
                "max_output_tokens": self.GEMINI_MAX_OUTPUT_TOKENS
            }
        }
    
    def validate(self):
        """验证配置"""
        errors = []
        
        # 检查Google AI认证配置
        if not self.GOOGLE_API_KEY and not os.path.exists(self.GOOGLE_SERVICE_ACCOUNT_PATH):
            errors.append("GOOGLE_API_KEY或GOOGLE_SERVICE_ACCOUNT_PATH必须设置其中一个")
        
        if self.GOOGLE_SERVICE_ACCOUNT_PATH and not os.path.exists(self.GOOGLE_SERVICE_ACCOUNT_PATH):
            errors.append(f"Service Account文件不存在: {self.GOOGLE_SERVICE_ACCOUNT_PATH}")
        
        if not os.path.exists(self.OUTPUT_DIR):
            try:
                Path(self.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"无法创建输出目录 {self.OUTPUT_DIR}: {str(e)}")
        
        if self.PORT < 1 or self.PORT > 65535:
            errors.append(f"无效的端口号: {self.PORT}")
        
        return errors

# 全局设置实例
settings = Settings()