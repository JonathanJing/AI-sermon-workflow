"""
Gemini AI客户端
使用Service Account进行Google AI Platform身份验证
"""

import os
import json
import google.generativeai as genai
from google.auth import credentials as google_credentials
from google.oauth2 import service_account
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

class GeminiClient:
    """Gemini AI客户端类"""
    
    def __init__(self, service_account_path: str = None, model_name: str = "gemini-2.5-pro"):
        """
        初始化Gemini客户端
        
        Args:
            service_account_path: Service Account JSON文件路径
            model_name: 模型名称，默认使用gemini-2.5-pro
        """
        self.model_name = model_name
        self.model = None
        self._setup_authentication(service_account_path)
        self._initialize_model()
    
    def _setup_authentication(self, service_account_path: str = None):
        """设置Google Cloud身份验证"""
        try:
            if service_account_path and os.path.exists(service_account_path):
                # 使用Service Account文件
                logger.info(f"使用Service Account文件: {service_account_path}")
                
                # 读取Service Account JSON
                with open(service_account_path, 'r') as f:
                    service_account_info = json.load(f)
                
                # 创建凭据
                credentials = service_account.Credentials.from_service_account_info(
                    service_account_info,
                    scopes=['https://www.googleapis.com/auth/generative-language']
                )
                
                # 配置Gemini
                genai.configure(credentials=credentials)
                
            elif 'GOOGLE_API_KEY' in os.environ:
                # 使用API Key
                logger.info("使用GOOGLE_API_KEY进行身份验证")
                genai.configure(api_key=os.environ['GOOGLE_API_KEY'])
                
            else:
                # 尝试使用默认凭据
                logger.info("尝试使用默认Google凭据")
                genai.configure()
                
        except Exception as e:
            logger.error(f"Google AI认证失败: {str(e)}")
            raise Exception(f"无法配置Google AI认证: {str(e)}")
    
    def _initialize_model(self):
        """初始化Gemini模型"""
        try:
            # 配置生成参数
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
            
            # 安全设置
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
            
            # 初始化模型
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            logger.info(f"成功初始化模型: {self.model_name}")
            
        except Exception as e:
            logger.error(f"模型初始化失败: {str(e)}")
            raise Exception(f"无法初始化Gemini模型: {str(e)}")
    
    def generate_content(self, prompt: str, **kwargs) -> str:
        """
        生成内容
        
        Args:
            prompt: 输入提示
            **kwargs: 额外的生成参数
            
        Returns:
            生成的文本内容
        """
        try:
            if not self.model:
                raise Exception("模型未初始化")
            
            # 生成内容
            response = self.model.generate_content(prompt)
            
            # 检查响应是否被安全过滤器阻止
            if not response.text:
                if response.prompt_feedback.block_reason:
                    raise Exception(f"内容被阻止: {response.prompt_feedback.block_reason}")
                else:
                    raise Exception("未收到有效响应")
            
            return response.text
            
        except Exception as e:
            logger.error(f"内容生成失败: {str(e)}")
            raise Exception(f"Gemini生成失败: {str(e)}")
    
    def generate_content_stream(self, prompt: str, **kwargs):
        """
        流式生成内容
        
        Args:
            prompt: 输入提示
            **kwargs: 额外的生成参数
            
        Yields:
            生成的文本片段
        """
        try:
            if not self.model:
                raise Exception("模型未初始化")
            
            # 流式生成
            response = self.model.generate_content(prompt, stream=True)
            
            for chunk in response:
                if chunk.text:
                    yield chunk.text
                    
        except Exception as e:
            logger.error(f"流式生成失败: {str(e)}")
            raise Exception(f"Gemini流式生成失败: {str(e)}")
    
    def chat_session(self, history: list = None):
        """
        创建聊天会话
        
        Args:
            history: 聊天历史记录
            
        Returns:
            聊天会话对象
        """
        try:
            if not self.model:
                raise Exception("模型未初始化")
            
            chat = self.model.start_chat(history=history or [])
            return chat
            
        except Exception as e:
            logger.error(f"创建聊天会话失败: {str(e)}")
            raise Exception(f"无法创建Gemini聊天会话: {str(e)}")
    
    def test_connection(self) -> Dict[str, Any]:
        """
        测试连接
        
        Returns:
            测试结果
        """
        try:
            # 发送简单的测试请求
            test_prompt = "你好，请简短回复确认你可以正常工作。"
            response = self.generate_content(test_prompt)
            
            return {
                "success": True,
                "model": self.model_name,
                "response": response[:100] + "..." if len(response) > 100 else response,
                "message": "连接测试成功"
            }
            
        except Exception as e:
            return {
                "success": False,
                "model": self.model_name,
                "error": str(e),
                "message": "连接测试失败"
            }
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息
        
        Returns:
            模型信息
        """
        try:
            # 获取可用模型列表
            models = genai.list_models()
            current_model_info = None
            
            for model in models:
                if self.model_name in model.name:
                    current_model_info = {
                        "name": model.name,
                        "display_name": model.display_name,
                        "description": model.description,
                        "input_token_limit": model.input_token_limit,
                        "output_token_limit": model.output_token_limit,
                        "supported_generation_methods": model.supported_generation_methods
                    }
                    break
            
            return {
                "current_model": current_model_info,
                "available_models": [model.name for model in models]
            }
            
        except Exception as e:
            logger.error(f"获取模型信息失败: {str(e)}")
            return {
                "current_model": None,
                "available_models": [],
                "error": str(e)
            }

def create_gemini_client(service_account_path: str = None, 
                        model_name: str = "gemini-2.5-pro") -> GeminiClient:
    """
    创建Gemini客户端的工厂函数
    
    Args:
        service_account_path: Service Account JSON文件路径
        model_name: 模型名称
        
    Returns:
        GeminiClient实例
    """
    return GeminiClient(service_account_path=service_account_path, model_name=model_name)

# 全局客户端实例（单例模式）
_global_client: Optional[GeminiClient] = None

def get_global_client() -> Optional[GeminiClient]:
    """获取全局Gemini客户端"""
    return _global_client

def set_global_client(client: GeminiClient):
    """设置全局Gemini客户端"""
    global _global_client
    _global_client = client

def initialize_global_client(service_account_path: str = None, 
                           model_name: str = "gemini-2.5-pro"):
    """初始化全局Gemini客户端"""
    global _global_client
    if _global_client is None:
        _global_client = create_gemini_client(service_account_path, model_name)
    return _global_client