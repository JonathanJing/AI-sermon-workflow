#!/usr/bin/env python3
"""
Gemini API连接测试脚本
用于验证API密钥配置是否正确
"""

import os
import sys
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.gemini_client import create_gemini_client

def test_gemini_connection():
    """测试Gemini API连接"""
    print("🔍 开始测试Gemini API连接...")
    print("=" * 50)
    
    # 检查可用的API密钥文件
    api_key_files = [
        'gemini-api-key.json',
        'api-key.json', 
        'google-api-key.json',
        'service-account.json'
    ]
    
    print("📁 检查API密钥文件:")
    found_files = []
    for file in api_key_files:
        if os.path.exists(file):
            print(f"  ✅ {file} - 存在")
            found_files.append(file)
        else:
            print(f"  ❌ {file} - 不存在")
    
    # 检查环境变量
    print("\n🔑 检查环境变量:")
    google_api_key = os.environ.get('GOOGLE_API_KEY', '')
    if google_api_key:
        print(f"  ✅ GOOGLE_API_KEY - 已设置 (长度: {len(google_api_key)})")
    else:
        print("  ❌ GOOGLE_API_KEY - 未设置")
    
    if not found_files and not google_api_key:
        print("\n❌ 错误: 未找到任何API密钥配置!")
        print("请确保以下任一方式:")
        print("1. 设置环境变量 GOOGLE_API_KEY")
        print("2. 创建包含API密钥的JSON文件 (gemini-api-key.json)")
        return False
    
    # 尝试创建客户端并测试连接
    print("\n🚀 测试Gemini客户端...")
    try:
        # 使用找到的第一个文件或默认路径
        api_file = found_files[0] if found_files else None
        
        print(f"  📝 使用配置文件: {api_file}")
        client = create_gemini_client(
            service_account_path=api_file,
            model_name="gemini-1.5-pro"  # 使用更稳定的模型进行测试
        )
        
        print("  ✅ 客户端创建成功")
        
        # 测试连接
        print("  🔗 测试API连接...")
        result = client.test_connection()
        
        if result['success']:
            print(f"  ✅ 连接测试成功!")
            print(f"  📋 模型: {result['model']}")
            print(f"  💬 测试响应: {result['response']}")
            
            # 获取模型信息
            print("\n📊 获取模型信息...")
            model_info = client.get_model_info()
            if model_info['current_model']:
                model = model_info['current_model']
                print(f"  📋 模型名称: {model.get('display_name', 'N/A')}")
                print(f"  📝 模型描述: {model.get('description', 'N/A')[:100]}...")
                print(f"  🔢 输入Token限制: {model.get('input_token_limit', 'N/A')}")
                print(f"  🔢 输出Token限制: {model.get('output_token_limit', 'N/A')}")
            
            return True
        else:
            print(f"  ❌ 连接测试失败: {result['error']}")
            return False
            
    except Exception as e:
        print(f"  ❌ 客户端创建失败: {str(e)}")
        return False

def main():
    """主函数"""
    print("🤖 Gemini API连接测试工具")
    print("=" * 50)
    
    success = test_gemini_connection()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 测试完成! Gemini API配置正确")
        print("✅ 你现在可以启动视频切片服务了")
        print("\n💡 启动命令:")
        print("   cd app && python main.py")
    else:
        print("❌ 测试失败! 请检查API密钥配置")
        print("\n🔧 解决方案:")
        print("1. 确保gemini-api-key.json文件存在且格式正确:")
        print('   {"api_key": "your_actual_api_key_here"}')
        print("2. 或设置环境变量:")
        print("   export GOOGLE_API_KEY=your_actual_api_key_here")
        print("3. 确保API密钥有效且有足够的配额")

if __name__ == "__main__":
    main()