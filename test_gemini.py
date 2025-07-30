#!/usr/bin/env python3
"""
Gemini客户端测试脚本
用于验证Gemini API连接和基本功能
"""

import os
import sys
import json
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "app"))

from app.services.gemini_client import GeminiClient

def test_gemini_connection():
    """测试Gemini连接"""
    print("🔍 测试Gemini API连接...")
    
    # 检查Service Account文件
    service_account_path = "service-account.json"
    if not os.path.exists(service_account_path):
        print(f"❌ Service Account文件不存在: {service_account_path}")
        print("请按照setup_guide_gemini.md的说明创建Service Account文件")
        return False
    
    try:
        # 创建客户端
        client = GeminiClient(service_account_path=service_account_path)
        print("✅ Gemini客户端创建成功")
        
        # 测试连接
        test_result = client.test_connection()
        if test_result['success']:
            print(f"✅ 连接测试成功: {test_result['message']}")
            print(f"📝 响应: {test_result['response']}")
            return True
        else:
            print(f"❌ 连接测试失败: {test_result['error']}")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return False

def test_simple_generation():
    """测试简单内容生成"""
    print("\n🧪 测试简单内容生成...")
    
    service_account_path = "service-account.json"
    if not os.path.exists(service_account_path):
        print("❌ Service Account文件不存在")
        return False
    
    try:
        client = GeminiClient(service_account_path=service_account_path)
        
        # 简单测试
        prompt = "请用一句话回答：今天天气怎么样？"
        response = client.generate_content(prompt)
        print(f"✅ 生成成功: {response}")
        return True
        
    except Exception as e:
        print(f"❌ 生成失败: {str(e)}")
        return False

def test_json_generation():
    """测试JSON格式生成"""
    print("\n📋 测试JSON格式生成...")
    
    service_account_path = "service-account.json"
    if not os.path.exists(service_account_path):
        print("❌ Service Account文件不存在")
        return False
    
    try:
        client = GeminiClient(service_account_path=service_account_path)
        
        # JSON格式测试
        prompt = """
        请分析以下文本并以JSON格式返回结果：
        
        文本：今天是一个美好的日子，阳光明媚，心情愉快。
        
        请返回JSON格式：
        {
            "sentiment": "positive",
            "keywords": ["美好", "阳光", "愉快"],
            "score": 0.8
        }
        """
        
        response = client.generate_content(prompt)
        print(f"📝 原始响应: {response}")
        
        # 尝试解析JSON
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                print(f"✅ JSON解析成功: {parsed}")
                return True
            else:
                print("⚠️ 响应中未找到JSON格式")
                return False
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败: {e}")
            return False
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    import re
    
    print("🚀 Gemini客户端测试开始\n")
    
    # 运行测试
    tests = [
        ("连接测试", test_gemini_connection),
        ("简单生成测试", test_simple_generation),
        ("JSON生成测试", test_json_generation)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"=== {test_name} ===")
        result = test_func()
        results.append((test_name, result))
        print()
    
    # 总结
    print("📊 测试结果总结:")
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
    
    success_count = sum(1 for _, result in results if result)
    print(f"\n🎯 总体结果: {success_count}/{len(results)} 测试通过")
    
    if success_count == len(results):
        print("🎉 所有测试通过！Gemini客户端工作正常。")
    else:
        print("⚠️ 部分测试失败，请检查配置和网络连接。") 