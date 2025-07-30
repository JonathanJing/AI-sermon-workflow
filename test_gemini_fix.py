#!/usr/bin/env python3
"""
测试并修复Gemini API连接问题
"""

import os
import sys
import json

# 添加项目路径
sys.path.append('app')

import google.generativeai as genai
from app.services.gemini_client import GeminiClient, initialize_global_client

def test_api_key_direct():
    """直接测试API key"""
    print("🔍 测试1: 直接API Key连接")
    try:
        with open('gemini-api-key.json', 'r') as f:
            key_data = json.load(f)
        
        api_key = key_data['api_key']
        print(f"✅ API Key读取成功: {api_key[:10]}...")
        
        # 配置API
        genai.configure(api_key=api_key)
        print("✅ API配置成功")
        
        # 测试可用模型
        print("\n🔍 测试gemini-2.5-pro模型:")
        model = genai.GenerativeModel('gemini-2.5-pro')
        response = model.generate_content("请回复'连接成功'")
        print(f"✅ 模型响应: {response.text}")
        
        return True
        
    except Exception as e:
        print(f"❌ 直接测试失败: {str(e)}")
        return False

def test_gemini_client():
    """测试Gemini客户端类"""
    print("\n🔍 测试2: GeminiClient类")
    try:
        client = GeminiClient(service_account_path='gemini-api-key.json', model_name='gemini-2.5-pro')
        print("✅ GeminiClient初始化成功")
        
        # 测试连接
        result = client.test_connection()
        if result['success']:
            print(f"✅ 连接测试成功: {result['response']}")
            return True
        else:
            print(f"❌ 连接测试失败: {result['error']}")
            return False
            
    except Exception as e:
        print(f"❌ GeminiClient测试失败: {str(e)}")
        return False

def test_global_client():
    """测试全局客户端初始化"""
    print("\n🔍 测试3: 全局客户端初始化")
    try:
        initialize_global_client(service_account_path='gemini-api-key.json', model_name='gemini-2.5-pro')
        print("✅ 全局客户端初始化成功")
        
        from app.services.gemini_client import get_global_client
        client = get_global_client()
        
        if client:
            test_result = client.test_connection()
            if test_result['success']:
                print(f"✅ 全局客户端测试成功: {test_result['response']}")
                return True
            else:
                print(f"❌ 全局客户端测试失败: {test_result['error']}")
                return False
        else:
            print("❌ 无法获取全局客户端")
            return False
            
    except Exception as e:
        print(f"❌ 全局客户端测试失败: {str(e)}")
        return False

def test_alternative_models():
    """测试其他可用模型"""
    print("\n🔍 测试4: 替代模型")
    
    alternative_models = [
        'gemini-1.5-pro',
        'gemini-2.0-flash',
        'gemini-1.5-flash'
    ]
    
    try:
        with open('gemini-api-key.json', 'r') as f:
            key_data = json.load(f)
        genai.configure(api_key=key_data['api_key'])
        
        for model_name in alternative_models:
            try:
                print(f"  测试模型: {model_name}")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content("Hello")
                print(f"  ✅ {model_name} 工作正常: {response.text[:20]}...")
            except Exception as e:
                print(f"  ❌ {model_name} 失败: {str(e)}")
    
    except Exception as e:
        print(f"❌ 替代模型测试失败: {str(e)}")

def fix_environment():
    """修复环境变量设置"""
    print("\n🔧 修复环境配置...")
    
    try:
        # 读取API key
        with open('gemini-api-key.json', 'r') as f:
            key_data = json.load(f)
        
        # 设置环境变量
        os.environ['GOOGLE_API_KEY'] = key_data['api_key']
        print("✅ 已设置GOOGLE_API_KEY环境变量")
        
        # 验证环境变量
        if 'GOOGLE_API_KEY' in os.environ:
            print("✅ 环境变量验证成功")
            return True
        else:
            print("❌ 环境变量设置失败")
            return False
            
    except Exception as e:
        print(f"❌ 修复环境失败: {str(e)}")
        return False

def main():
    print("🚀 Gemini API连接诊断和修复工具")
    print("=" * 50)
    
    # 测试序列
    tests = [
        ("API Key直接连接", test_api_key_direct),
        ("GeminiClient类", test_gemini_client),
        ("全局客户端", test_global_client),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        success = test_func()
        results.append((test_name, success))
        
        if success:
            print(f"✅ {test_name} 通过")
            break  # 如果某个测试通过了，就不需要继续
        else:
            print(f"❌ {test_name} 失败")
    
    # 如果所有测试都失败了，尝试替代方案
    if not any(result[1] for result in results):
        print(f"\n{'='*50}")
        print("🔄 尝试替代解决方案...")
        
        # 修复环境变量
        if fix_environment():
            # 重新测试全局客户端
            test_global_client()
        
        # 测试其他模型
        test_alternative_models()
    
    print(f"\n{'='*50}")
    print("📊 测试结果摘要:")
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {test_name}: {status}")
    
    # 提供解决方案
    if any(result[1] for result in results):
        print("\n🎉 连接问题已解决！")
        print("💡 建议: 重启服务以确保更改生效")
    else:
        print("\n🔧 建议的解决方案:")
        print("1. 检查API key是否有效")
        print("2. 确认模型名称是否正确")
        print("3. 检查网络连接")
        print("4. 尝试使用gemini-1.5-pro替代gemini-2.5-pro")

if __name__ == "__main__":
    main()