"""
AI视频自动切片系统主应用
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import os
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 首先确保API key环境变量设置正确
def setup_api_key():
    """设置API key环境变量"""
    import json
    
    # 如果环境变量已设置，优先使用
    if os.getenv('GOOGLE_API_KEY'):
        print("✅ 使用环境变量中的GOOGLE_API_KEY")
        return True
    
    # 尝试从文件读取API key
    api_key_files = ['gemini-api-key.json', 'api-key.json', 'google-api-key.json']
    
    for key_file in api_key_files:
        key_path = os.path.join(project_root, key_file)
        if os.path.exists(key_path):
            try:
                with open(key_path, 'r') as f:
                    key_data = json.load(f)
                
                if 'api_key' in key_data and key_data['api_key']:
                    os.environ['GOOGLE_API_KEY'] = key_data['api_key']
                    print(f"✅ 从{key_file}读取API key并设置环境变量")
                    return True
                    
            except Exception as e:
                print(f"❌ 读取{key_file}失败: {str(e)}")
                continue
    
    print("❌ 未找到有效的API key")
    return False

# 设置API key
setup_api_key()

from app.routers import video_clipping
from app.services.gemini_client import initialize_global_client
from app.config import settings

# 初始化Gemini客户端
try:
    initialize_global_client(
        service_account_path=settings.GOOGLE_SERVICE_ACCOUNT_PATH,
        model_name=settings.GEMINI_MODEL
    )
    print(f"✅ Gemini客户端初始化成功: {settings.GEMINI_MODEL}")
except Exception as e:
    print(f"❌ Gemini客户端初始化失败: {str(e)}")
    print("🔧 尝试修复...")
    
    # 尝试使用备选模型
    try:
        initialize_global_client(
            service_account_path=settings.GOOGLE_SERVICE_ACCOUNT_PATH,
            model_name="gemini-1.5-pro"
        )
        print("✅ 使用备选模型 gemini-1.5-pro 初始化成功")
    except Exception as e2:
        print(f"❌ 备选模型也失败: {str(e2)}")
        print("请检查API密钥配置和网络连接")

# 创建FastAPI应用实例
app = FastAPI(
    title="AI视频自动切片系统",
    description="基于SRT字幕文件和Gemini 2.5-pro的视频自动切片系统",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含路由
app.include_router(video_clipping.router)

# 静态文件服务（用于提供生成的视频文件）
if os.path.exists("data/clips"):
    app.mount("/clips", StaticFiles(directory="data/clips"), name="clips")

@app.get("/", summary="系统信息")
async def root():
    """获取系统基本信息"""
    return {
        "name": "AI视频自动切片系统",
        "version": "1.0.0",
        "description": "基于SRT字幕文件和生成式AI的视频自动切片系统",
        "features": [
            "SRT字幕文件解析",
            "AI智能语义切片",
            "视频自动切割",
            "质量评分验证",
            "标题标签生成",
            "社交媒体优化"
        ],
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "video_clipping": "/video-clipping"
        }
    }

@app.get("/health", summary="健康检查")
async def health_check():
    """系统健康检查"""
    return {
        "status": "healthy",
        "timestamp": str(datetime.now())
    }

@app.exception_handler(404)
async def not_found_handler(request, exc):
    """404错误处理"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "资源未找到",
            "message": "请检查请求路径是否正确",
            "docs_url": "/docs"
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """500错误处理"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "服务器内部错误",
            "message": "请联系系统管理员或查看日志",
            "support": "https://github.com/your-repo/issues"
        }
    )

if __name__ == "__main__":
    import uvicorn
    
    # 确保必要的目录存在
    os.makedirs("data/clips", exist_ok=True)
    os.makedirs("data/uploads", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    # 启动服务
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )