#!/usr/bin/env python3
"""
快速测试脚本 - 直接开始使用，无需配置
"""

import requests
import json
import time
import os

BASE_URL = "http://localhost:8000"

def test_system():
    """测试系统是否ready"""
    print("🚀 测试AI视频切片系统...")
    
    # 1. 健康检查
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ 系统运行正常")
        else:
            print("❌ 系统响应异常")
            return False
    except requests.ConnectionError:
        print("❌ 无法连接到服务，请确保服务已启动")
        print("💡 运行: python app/main.py")
        return False
    
    # 2. 检查服务状态
    try:
        response = requests.get(f"{BASE_URL}/video-clipping/summary")
        if response.status_code == 200:
            data = response.json()
            if data.get('service_configured'):
                print("✅ Gemini客户端已配置")
                print(f"📁 输出目录: {data.get('output_directory')}")
            else:
                print("❌ Gemini客户端未配置，请检查API密钥")
                return False
        else:
            print("❌ 服务状态检查失败")
            return False
    except Exception as e:
        print(f"❌ 服务检查出错: {str(e)}")
        return False
    
    print("\n🎉 系统ready！可以开始处理视频了")
    print("\n📖 使用方法:")
    print("1. 准备SRT字幕文件和视频文件")
    print("2. 使用POST请求上传到 /video-clipping/upload")
    print("3. 或访问 http://localhost:8000/docs 查看API文档")
    
    return True

def demo_upload():
    """演示文件上传（如果有测试文件）"""
    print("\n🎬 查找测试文件...")
    
    # 查找现有的测试文件
    test_files = []
    for root, dirs, files in os.walk("data"):
        for file in files:
            if file.endswith('.srt'):
                test_files.append(os.path.join(root, file))
                break
    
    if test_files:
        print(f"📄 找到SRT文件: {test_files[0]}")
        print("💡 你可以用curl测试:")
        print(f"""
curl -X POST "{BASE_URL}/video-clipping/upload" \\
  -F "srt_file=@{test_files[0]}" \\
  -F "video_file=@your_video.mp4" \\
  -F "target_count=3" \\
  -F "min_duration=15" \\
  -F "max_duration=45"
        """)
    else:
        print("📄 未找到SRT测试文件")
        print("💡 将SRT和视频文件放到data目录中测试")

if __name__ == "__main__":
    print("🤖 AI视频自动切片系统 - 快速测试")
    print("=" * 50)
    
    if test_system():
        demo_upload()
    
    print("\n" + "=" * 50)
    print("🔗 有用的链接:")
    print(f"• API文档: {BASE_URL}/docs")
    print(f"• 系统状态: {BASE_URL}/video-clipping/summary") 
    print(f"• 健康检查: {BASE_URL}/health")