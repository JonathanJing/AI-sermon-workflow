# 🚀 简单使用指南

**KISS原则**: Keep It Simple, Stupid! 不需要复杂配置，开箱即用。

## 快速开始 (3步)

### 1️⃣ 启动服务
```bash
python main.py
```
服务自动启动在 `http://localhost:8000`

### 2️⃣ 上传文件
```bash
curl -X POST "http://localhost:8000/video-clipping/upload" \
  -F "srt_file=@your_subtitle.srt" \
  -F "video_file=@your_video.mp4"
```

### 3️⃣ 等待结果
系统自动处理，生成切片视频。

## 就这么简单！

### 🔧 测试系统
```bash
python quick_test.py
```

### 📖 查看API文档
访问: http://localhost:8000/docs

### 📁 结果文件
生成的视频在 `data/clips/` 目录

## 默认配置

- **模型**: Gemini 2.5-pro
- **切片数量**: 5个
- **时长**: 10-60秒
- **自动**: 质量评分 + 标题生成 + 标签

## 无需配置

系统启动时自动:
- ✅ 读取API密钥 (`gemini-api-key.json`)
- ✅ 初始化Gemini客户端
- ✅ 创建输出目录
- ✅ 准备所有服务

## API接口

### 上传并处理
```
POST /video-clipping/upload
```

### 查看任务状态  
```
GET /video-clipping/status/{job_id}
```

### 下载结果
```
GET /video-clipping/download/{job_id}/{clip_index}
```

## 就是这么简单！ 🎉

不需要复杂配置，不需要学习复杂API，直接开始使用。