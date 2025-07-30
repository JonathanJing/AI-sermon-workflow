#!/usr/bin/env python3
"""
AI视频切片服务启动脚本
修复了API连接问题，包含完整的提示词配置系统
"""

import uvicorn
import sys
import os
import json
from pathlib import Path

def main():
    print("🚀 AI视频自动切片系统")
    print("=" * 50)
    
    # 确保在项目根目录
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # 添加app目录到Python路径
    sys.path.insert(0, str(project_root / 'app'))
    
    # 检查API key
    api_key_file = project_root / 'gemini-api-key.json'
    if api_key_file.exists():
        try:
            with open(api_key_file, 'r') as f:
                key_data = json.load(f)
            if 'api_key' in key_data:
                print("✅ API密钥文件已找到")
            else:
                print("❌ API密钥文件格式错误")
                return
        except Exception as e:
            print(f"❌ 读取API密钥失败: {str(e)}")
            return
    else:
        print("❌ 未找到gemini-api-key.json文件")
        print("请确保API密钥文件存在")
        return
    
    # 导入应用
    try:
        from main import app
        print("✅ 应用模块加载成功")
    except Exception as e:
        print(f"❌ 应用模块加载失败: {str(e)}")
        return
    
    # 检查端口
    port = 8000
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        
        if result == 0:
            print(f"⚠️  端口{port}已被占用，使用端口8001")
            port = 8001
    except Exception:
        pass
    
    print(f"🌐 启动服务: http://localhost:{port}")
    print("📖 API文档: http://localhost:{port}/docs")
    print("🎯 切片上传: http://localhost:{port}/video-clipping/upload")
    print()
    print("💡 新功能:")
    print("  • 修复了时间分布问题 - 切片不再集中在前几分钟")
    print("  • 可调优的提示词配置系统")
    print("  • 使用 python tune_clips.py 进行快速调优")
    print()
    print("🔧 可用的API端点:")
    print("  • POST /video-clipping/upload - 上传文件并处理")
    print("  • POST /video-clipping/reprocess/{job_id} - 重新处理任务")
    print("  • GET /video-clipping/status/{job_id} - 查看处理状态")
    print("  • GET /video-clipping/download/{job_id}/{index} - 下载结果")
    print()
    print("按 Ctrl+C 停止服务")
    print("=" * 50)
    
    # 启动服务
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"\n❌ 服务启动失败: {str(e)}")

if __name__ == "__main__":
    main()