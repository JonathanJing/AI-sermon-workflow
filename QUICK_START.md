# 🚀 AI视频自动切片系统 - 快速启动指南

## ✅ 系统状态

恭喜！系统已经成功修复并运行。所有依赖问题已解决，Gemini客户端正常工作。

## 🔑 获取Google API Key

要完成配置，您需要获取一个有效的Google API Key：

### 方法1：Google AI Studio（推荐）

1. 访问 [Google AI Studio](https://makersuite.google.com/app/apikey)
2. 点击 "Create API Key"
3. 复制生成的API Key

### 方法2：Google Cloud Console

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建新项目或选择现有项目
3. 启用 "Generative Language API"
4. 在 "Credentials" 页面创建API Key

## ⚙️ 配置API Key

### 方法1：环境变量

```bash
export GOOGLE_API_KEY="your-actual-api-key"
```

### 方法2：配置文件

```bash
echo '{"api_key": "your-actual-api-key"}' > gemini-api-key.json
```

## 🚀 启动系统

### 使用启动脚本（推荐）

```bash
./start_server.sh
```

### 手动启动

```bash
source .venv/bin/activate
cd app && python3 main.py
```

## 🧪 测试系统

1. **健康检查**

```bash
curl http://localhost:8000/health
```

2. **配置API**

```bash
curl -X POST "http://localhost:8000/video-clipping/config" \
  -H "Content-Type: application/json" \
  -d '{"service_account_path": "../gemini-api-key.json", "model": "gemini-2.5-pro"}'
```

3. **查看API文档**

- 浏览器访问: http://localhost:8000/docs
- 或访问: http://localhost:8000/redoc

## 📁 项目结构

```
AI-sermon-workflow/
├── app/                    # 主应用目录
│   ├── main.py            # FastAPI应用入口
│   ├── config.py          # 配置管理
│   ├── routers/           # API路由
│   └── services/          # 业务逻辑服务
├── data/                  # 数据目录
│   ├── clips/            # 生成的视频片段
│   └── uploads/          # 上传的文件
├── requirements.txt       # Python依赖
├── start_server.sh       # 启动脚本
├── test_gemini.py        # Gemini测试脚本
└── gemini-api-key.json   # API Key配置
```

## 🔧 故障排除

### 问题：Python命令未找到

**解决方案**：使用 `python3` 而不是 `python`

```bash
python3 main.py
```

### 问题：API Key无效

**解决方案**：确保使用有效的Google API Key

- 检查API Key是否正确复制
- 确认Google Cloud项目已启用Generative Language API

### 问题：依赖安装失败

**解决方案**：重新安装依赖

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## 📚 更多信息

- 详细文档：查看 `readme_cn.md`
- Gemini配置指南：查看 `setup_guide_gemini.md`
- API文档：访问 http://localhost:8000/docs

## 🎉 完成！

系统现在已经完全可用！只需要一个有效的Google API Key就可以开始使用AI视频自动切片功能了。
