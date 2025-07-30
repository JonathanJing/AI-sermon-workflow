#!/usr/bin/env python3
"""
API密钥设置助手
帮助用户正确配置Gemini API密钥
"""

import os
import json
import sys
import datetime

def setup_api_key():
    """设置API密钥"""
    print("🔑 Gemini API密钥配置助手")
    print("=" * 40)
    
    # 检查现有配置
    api_key_files = ['gemini-api-key.json', 'api-key.json', 'google-api-key.json']
    existing_files = [f for f in api_key_files if os.path.exists(f)]
    
    if existing_files:
        print("📁 发现现有API密钥文件:")
        for file in existing_files:
            print(f"  ✅ {file}")
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                if 'api_key' in data and data['api_key']:
                    api_key = data['api_key']
                    print(f"     API Key: {api_key[:20]}...{api_key[-10:]} (长度: {len(api_key)})")
                else:
                    print("     ❌ 文件中没有找到有效的api_key字段")
            except Exception as e:
                print(f"     ❌ 读取文件失败: {str(e)}")
    
    # 检查环境变量
    env_key = os.environ.get('GOOGLE_API_KEY', '')
    if env_key:
        print(f"\n🌍 环境变量GOOGLE_API_KEY已设置 (长度: {len(env_key)})")
    
    # 如果已有配置，询问是否重新配置
    if existing_files or env_key:
        choice = input("\n是否要重新配置API密钥? (y/N): ").lower()
        if choice not in ['y', 'yes']:
            print("保持现有配置")
            return
    
    print("\n📝 请选择配置方式:")
    print("1. 创建JSON文件 (推荐)")
    print("2. 设置环境变量")
    print("3. 退出")
    
    choice = input("请选择 (1-3): ").strip()
    
    if choice == '1':
        setup_json_file()
    elif choice == '2':
        setup_environment_variable()
    elif choice == '3':
        print("退出配置")
        return
    else:
        print("❌ 无效选择")
        return

def setup_json_file():
    """设置JSON文件"""
    print("\n📄 创建JSON配置文件")
    print("-" * 30)
    
    # 获取API密钥
    api_key = input("请输入你的Gemini API密钥: ").strip()
    
    if not api_key:
        print("❌ API密钥不能为空")
        return
    
    # 验证API密钥格式 (Google API密钥通常以AIza开头)
    if not api_key.startswith('AIza'):
        print("⚠️  警告: API密钥格式可能不正确 (Google API密钥通常以'AIza'开头)")
        confirm = input("是否继续? (y/N): ").lower()
        if confirm not in ['y', 'yes']:
            return
    
    # 选择文件名
    filename = input("文件名 (默认: gemini-api-key.json): ").strip() or "gemini-api-key.json"
    
    if not filename.endswith('.json'):
        filename += '.json'
    
    # 创建JSON数据
    api_data = {
        "api_key": api_key,
        "created_at": str(datetime.datetime.now()),
        "note": "Gemini API密钥配置文件"
    }
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(api_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 成功创建配置文件: {filename}")
        print(f"📋 API密钥长度: {len(api_key)}")
        
        # 设置文件权限 (仅用户可读写)
        try:
            os.chmod(filename, 0o600)
            print("🔒 已设置文件权限为用户只读")
        except:
            print("⚠️  无法设置文件权限 (可能在Windows系统上)")
        
        # 添加到.gitignore
        add_to_gitignore(filename)
        
    except Exception as e:
        print(f"❌ 创建文件失败: {str(e)}")

def setup_environment_variable():
    """设置环境变量"""
    print("\n🌍 设置环境变量")
    print("-" * 30)
    
    api_key = input("请输入你的Gemini API密钥: ").strip()
    
    if not api_key:
        print("❌ API密钥不能为空")
        return
    
    # 验证API密钥格式
    if not api_key.startswith('AIza'):
        print("⚠️  警告: API密钥格式可能不正确")
        confirm = input("是否继续? (y/N): ").lower()
        if confirm not in ['y', 'yes']:
            return
    
    print("\n请选择设置方式:")
    print("1. 临时设置 (当前会话有效)")
    print("2. 永久设置 (添加到shell配置文件)")
    
    choice = input("请选择 (1-2): ").strip()
    
    if choice == '1':
        os.environ['GOOGLE_API_KEY'] = api_key
        print("✅ 临时环境变量已设置")
        print("💡 要永久设置，请运行:")
        print(f"   export GOOGLE_API_KEY='{api_key}'")
        
    elif choice == '2':
        shell_files = ['~/.bashrc', '~/.zshrc', '~/.profile']
        
        print("\n将添加到以下文件 (如果存在):")
        for shell_file in shell_files:
            expanded_path = os.path.expanduser(shell_file)
            if os.path.exists(expanded_path):
                try:
                    with open(expanded_path, 'a') as f:
                        f.write(f"\n# Gemini API Key\nexport GOOGLE_API_KEY='{api_key}'\n")
                    print(f"  ✅ {shell_file}")
                except Exception as e:
                    print(f"  ❌ {shell_file}: {str(e)}")
            else:
                print(f"  ⏭️  {shell_file} (不存在)")
        
        print("\n✅ 环境变量已添加到shell配置文件")
        print("💡 请重新加载shell或重启终端使配置生效")
    else:
        print("❌ 无效选择")

def add_to_gitignore(filename):
    """将文件添加到.gitignore"""
    gitignore_path = '.gitignore'
    
    try:
        # 读取现有.gitignore
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r') as f:
                content = f.read()
        else:
            content = ""
        
        # 检查是否已存在
        if filename not in content:
            with open(gitignore_path, 'a') as f:
                if content and not content.endswith('\n'):
                    f.write('\n')
                f.write(f"# API密钥文件\n{filename}\n")
            print(f"📝 已将{filename}添加到.gitignore")
        else:
            print(f"📝 {filename}已在.gitignore中")
            
    except Exception as e:
        print(f"⚠️  无法更新.gitignore: {str(e)}")

def main():
    """主函数"""
    try:
        setup_api_key()
        
        print("\n🎉 配置完成!")
        print("\n🧪 建议运行测试脚本验证配置:")
        print("   python test_gemini_connection.py")
        
    except KeyboardInterrupt:
        print("\n\n👋 用户取消配置")
    except Exception as e:
        print(f"\n❌ 配置过程中出现错误: {str(e)}")

if __name__ == "__main__":
    main()