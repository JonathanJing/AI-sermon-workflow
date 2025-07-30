#!/bin/bash

# AI视频自动切片系统启动脚本

echo "🚀 启动AI视频自动切片系统..."

# 检查虚拟环境是否存在
if [ ! -d ".venv" ]; then
    echo "❌ 虚拟环境不存在，请先运行: python3 -m venv .venv"
    exit 1
fi

# 激活虚拟环境
echo "📦 激活虚拟环境..."
source .venv/bin/activate

# 检查依赖是否已安装
if ! python3 -c "import fastapi, google.generativeai" 2>/dev/null; then
    echo "📥 安装依赖包..."
    pip install -r requirements.txt
fi

# 创建必要的目录
echo "📁 创建必要目录..."
mkdir -p data/clips
mkdir -p data/uploads
mkdir -p logs

# 启动服务器
echo "🌐 启动FastAPI服务器..."
cd app && python3 main.py 