# AI视频自动切片系统

一个基于SRT字幕文件和Google Gemini 2.5-pro的智能视频切片系统，可以自动将长视频切分为若干精彩的短视频片段，并为每个片段生成标题、标签和质量评分。

## 📋 项目概述

本系统通过分析SRT字幕文件，使用Google Gemini 2.5-pro识别语义完整的内容段落，自动切割视频并生成适合社交媒体传播的短视频内容。系统采用Service Account认证方式，提供完整的质量评估、标题生成和标签系统，大大提高了视频内容创作的效率。

## ✨ 核心功能

### 🎯 智能切片
- **SRT解析**: 精确解析字幕文件，提取时间戳和文本内容
- **AI语义分析**: 使用Gemini 2.5-pro模型识别语义完整的段落
- **智能切片**: 基于内容质量和时长要求自动切分视频
- **时长控制**: 支持自定义最小/最大时长（默认10-60秒）

### 🔍 质量评估
- **技术质量检测**: 分辨率、比特率、帧率、文件大小检查
- **内容质量分析**: 完整性、信息密度、吸引力评估
- **音频质量检测**: 音量水平、静音检测
- **AI内容评分**: 基于多维度的智能内容质量评分
- **综合评分**: 0-1分的综合质量评分系统

### 📝 标题与标签
- **智能标题生成**: 5种不同风格的标题选项
  - 吸引眼球型
  - 描述性
  - 疑问式  
  - 数字式
  - 励志型
- **标签系统**: 基于内容自动生成相关标签
- **社交媒体优化**: 适合各平台传播的标题和标签格式
- **关键词提取**: 基于jieba分词的中文关键词提取

### 🌐 完整API
- **RESTful API**: 完整的HTTP API接口
- **文件上传**: 支持SRT和视频文件在线上传
- **任务管理**: 异步任务处理和状态跟踪
- **结果下载**: 直接下载生成的视频片段
- **批量处理**: 支持批量视频处理

## 🏗️ 系统架构

```
AI视频自动切片系统/
├── app/
│   ├── main.py                 # 主应用入口
│   ├── config.py              # 配置管理
│   ├── routers/
│   │   └── video_clipping.py  # API路由
│   └── services/
│       └── video_clipping/
│           ├── srt_parser.py      # SRT解析器
│           ├── ai_slicer.py       # AI切片算法
│           ├── video_cutter.py    # 视频切割器
│           ├── validator.py       # 质量验证器
│           └── title_tagger.py    # 标题标签生成器
├── data/
│   ├── clips/                 # 生成的视频片段
│   ├── uploads/               # 上传文件
│   └── processed/             # 已处理数据
├── requirements.txt           # 依赖包
├── .env.example              # 环境变量示例
└── readme_cn.md              # 项目文档
```

## 🚀 快速开始

### 环境要求

- Python 3.8+
- FFmpeg (用于视频处理)
- Google Cloud Service Account或Google API密钥
- Gemini 2.5-pro访问权限

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd AI-sermon-workflow
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **安装FFmpeg**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# 下载FFmpeg并添加到系统PATH
```

4. **配置环境变量**
```bash
cp .env.example .env
# 编辑.env文件，配置Google Service Account路径或API密钥
# 将你的service-account.json文件放在项目根目录
```

5. **启动服务**
```bash
cd app
python main.py
```

服务将在 `http://localhost:8000` 启动

### 快速测试

1. **访问API文档**: http://localhost:8000/docs
2. **配置服务**:
```bash
curl -X POST "http://localhost:8000/video-clipping/config" \
  -H "Content-Type: application/json" \
  -d '{
    "service_account_path": "service-account.json",
    "model": "gemini-2.5-pro",
    "output_dir": "data/clips"
  }'
```

3. **上传文件并创建切片任务**:
```bash
curl -X POST "http://localhost:8000/video-clipping/upload" \
  -F "srt_file=@your_subtitle.srt" \
  -F "video_file=@your_video.mp4" \
  -F "min_duration=10" \
  -F "max_duration=60" \
  -F "target_count=5"
```

## 📖 详细使用指南

### API接口说明

#### 1. 配置服务
```http
POST /video-clipping/config
Content-Type: application/json

{
  "service_account_path": "service-account.json",
  "google_api_key": "",
  "model": "gemini-2.5-pro",
  "output_dir": "data/clips",
  "quality_thresholds": {},
  "gemini_config": {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 40,
    "max_output_tokens": 2048
  }
}
```

#### 2. 创建切片任务
```http
POST /video-clipping/clip
Content-Type: application/json

{
  "srt_file_path": "/path/to/subtitle.srt",
  "video_file_path": "/path/to/video.mp4",
  "min_duration": 10.0,
  "max_duration": 60.0,
  "target_count": 5,
  "enable_validation": true,
  "enable_title_generation": true,
  "quality_threshold": 0.5
}
```

#### 3. 上传文件（推荐）
```http
POST /video-clipping/upload
Content-Type: multipart/form-data

srt_file: [文件]
video_file: [文件]
min_duration: 10.0
max_duration: 60.0  
target_count: 5
enable_validation: true
enable_title_generation: true
```

#### 4. 查询任务状态
```http
GET /video-clipping/status/{job_id}
```

#### 5. 获取任务结果
```http
GET /video-clipping/results/{job_id}
```

#### 6. 下载视频片段
```http
GET /video-clipping/download/{job_id}/{clip_index}
```

### 参数配置说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| min_duration | float | 10.0 | 最小片段时长（秒） |
| max_duration | float | 60.0 | 最大片段时长（秒） |
| target_count | int | 5 | 目标片段数量 |
| enable_validation | bool | true | 是否启用质量验证 |
| enable_title_generation | bool | true | 是否生成标题标签 |
| quality_threshold | float | 0.5 | 质量分数阈值 |

## 📊 质量评分体系

系统采用多维度质量评分机制：

### 技术质量（25%权重）
- 文件大小检查
- 分辨率检查（最低480p）
- 比特率检查
- 帧率检查（最低15fps）

### 内容质量（30%权重）
- 文本长度适中性
- 内容完整性评分
- 观众吸引力评分
- 话题专注度评分

### 时长质量（15%权重）
- 理想时长范围：15-60秒
- 可接受范围：10-90秒
- 过短或过长都会降分

### 音频质量（15%权重）
- 音量水平检测
- 静音段检测
- 音频编码质量

### AI内容分析（15%权重）
- 语言流畅性
- 信息密度
- 情感表达
- 话题连贯性

## 🎨 标题生成策略

系统提供5种不同风格的标题：

1. **吸引眼球型**: 突出情感冲击力，使用强烈词汇
2. **描述性**: 准确概括内容，信息明确
3. **疑问式**: 引发思考，激发好奇心
4. **数字式**: 包含具体数字，增加可信度
5. **励志型**: 传递正能量，激励观众

### 标题评分因素
- 长度适中（8-20字最佳）
- 关键词匹配度
- 情感表达强度
- 社交媒体友好度
- 避免平淡用词

## 🏷️ 标签系统

### 标签来源
1. **AI生成标签**: 基于内容语义分析
2. **关键词标签**: jieba分词提取
3. **预定义标签**: 内置标签库匹配
4. **分类标签**: 按主题、情感、场景分类

### 预定义标签库
- **宗教类**: 基督教、信仰、圣经、祷告等
- **情感类**: 感动、温暖、治愈、励志等  
- **生活类**: 人生、智慧、成长、家庭等
- **节日类**: 圣诞节、复活节、感恩节等
- **主题类**: 爱、希望、宽恕、救赎等

## 🔧 配置选项

### 环境变量配置

```bash
# Google AI配置
GOOGLE_SERVICE_ACCOUNT_PATH=service-account.json
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_MODEL=gemini-2.5-pro

# 服务配置  
HOST=0.0.0.0
PORT=8000
DEBUG=True

# 文件路径配置
OUTPUT_DIR=data/clips
UPLOAD_DIR=data/uploads
LOG_DIR=logs

# 切片参数
DEFAULT_MIN_DURATION=10.0
DEFAULT_MAX_DURATION=60.0
DEFAULT_TARGET_COUNT=5

# Gemini配置参数
GEMINI_TEMPERATURE=0.7
GEMINI_TOP_P=0.8
GEMINI_TOP_K=40
GEMINI_MAX_OUTPUT_TOKENS=2048

# 质量阈值
MIN_FILE_SIZE=1024
MIN_RESOLUTION=480
MIN_BITRATE=100000
MIN_AUDIO_LEVEL=-30.0
CONTENT_SCORE_THRESHOLD=0.3

# 安全配置
MAX_FILE_SIZE=500MB
ALLOWED_VIDEO_FORMATS=mp4,avi,mov,mkv
ALLOWED_SUBTITLE_FORMATS=srt,vtt
```

### 质量阈值自定义

可以通过API调整质量检测阈值：

```json
{
  "quality_thresholds": {
    "min_duration": 5.0,
    "max_duration": 90.0,
    "min_file_size": 2048,
    "min_resolution": 720,
    "min_bitrate": 200000,
    "audio_level": -25.0,
    "content_score": 0.4
  }
}
```

## 📋 返回结果格式

### 切片结果示例

```json
{
  "job_id": "uuid-string",
  "clips": [
    {
      "clip_id": "uuid-string",
      "index": 1,
      "output_path": "data/clips/clip_01_uuid.mp4",
      "start_time": 15.5,
      "duration": 45.2,
      "end_time": 60.7,
      "file_size": 2048576,
      "video_info": {
        "width": 1920,
        "height": 1080,
        "fps": 25.0,
        "bitrate": 2500000
      },
      "quality_score": 0.82,
      "title": "生活中的智慧启示",
      "tags": ["智慧", "人生", "启示", "成长"],
      "social_media": {
        "primary_title": "生活中的智慧启示",
        "hashtags": "#智慧 #人生 #启示 #成长 #正能量",
        "description": "深刻的人生感悟，值得反思...",
        "social_media_text": "🎬 生活中的智慧启示\n\n深刻的人生感悟，值得反思...\n\n#智慧 #人生 #启示 #成长 #正能量\n\n#短视频 #精彩片段 #值得收藏"
      },
      "validation": {
        "valid": true,
        "score": 0.82,
        "issues": [],
        "details": {
          "technical": {...},
          "content": {...},
          "duration": {...},
          "audio": {...}
        }
      },
      "success": true
    }
  ],
  "summary": {
    "total_clips": 5,
    "successful_clips": 4,
    "failed_clips": 1,
    "total_duration": 245.8,
    "average_quality_score": 0.76
  },
  "validation": {
    "total_clips": 5,
    "valid_clips": 4,
    "invalid_clips": 1,
    "average_score": 0.76,
    "common_issues": {
      "音量过低": 1
    },
    "recommendations": [
      "建议调整音频录制设备或后期处理音量"
    ]
  }
}
```

## 🚀 高级用法

### 批量处理

使用Python SDK进行批量处理：

```python
import requests
import os

# 配置服务
config_data = {
    "openai_api_key": "your-api-key",
    "model": "gpt-3.5-turbo", 
    "output_dir": "data/clips"
}
requests.post("http://localhost:8000/video-clipping/config", json=config_data)

# 批量处理文件
video_files = ["video1.mp4", "video2.mp4", "video3.mp4"]
srt_files = ["video1.srt", "video2.srt", "video3.srt"]

job_ids = []
for video_file, srt_file in zip(video_files, srt_files):
    with open(video_file, 'rb') as vf, open(srt_file, 'rb') as sf:
        files = {
            'video_file': vf,
            'srt_file': sf
        }
        data = {
            'min_duration': 15,
            'max_duration': 45,
            'target_count': 3
        }
        response = requests.post(
            "http://localhost:8000/video-clipping/upload",
            files=files,
            data=data
        )
        job_ids.append(response.json()['job_id'])

# 监控处理进度
for job_id in job_ids:
    while True:
        status = requests.get(f"http://localhost:8000/video-clipping/status/{job_id}")
        if status.json()['status'] == 'completed':
            break
        time.sleep(5)
```

### 自定义切片策略

```python
# 自定义切片请求
custom_request = {
    "srt_file_path": "/path/to/subtitle.srt",
    "video_file_path": "/path/to/video.mp4",
    "min_duration": 20.0,      # 更长的最小时长
    "max_duration": 90.0,      # 更长的最大时长
    "target_count": 10,        # 更多片段
    "enable_validation": True,
    "enable_title_generation": True,
    "quality_threshold": 0.7   # 更高的质量要求
}
```

### 质量过滤

```python
# 获取结果并过滤高质量片段
results = requests.get(f"http://localhost:8000/video-clipping/results/{job_id}").json()

high_quality_clips = [
    clip for clip in results['clips'] 
    if clip.get('quality_score', 0) >= 0.8 and clip.get('success', False)
]

print(f"找到 {len(high_quality_clips)} 个高质量片段")
```

## 🐛 故障排除

### 常见问题

1. **Gemini API调用失败**
   - 检查Service Account文件是否存在且有效
   - 确认Google Cloud项目已启用Gemini API
   - 检查Service Account权限是否正确
   - 验证网络连接和防火墙设置

2. **FFmpeg错误**
   - 确认FFmpeg已正确安装
   - 检查视频文件格式是否支持
   - 验证文件路径是否正确

3. **内存不足**
   - 减少并发处理数量
   - 降低视频分辨率
   - 增加系统内存

4. **切片质量低**
   - 调整质量阈值
   - 检查原视频质量
   - 优化SRT文件质量

### 日志分析

```bash
# 查看详细日志
tail -f logs/app.log

# 过滤错误日志
grep "ERROR" logs/app.log

# 查看特定任务日志
grep "job_id" logs/app.log
```

## 🔧 开发指南

### 项目结构说明

- `srt_parser.py`: SRT文件解析，支持多种编码格式
- `ai_slicer.py`: AI智能切片核心算法
- `video_cutter.py`: 视频切割和后处理
- `validator.py`: 多维度质量评估系统
- `title_tagger.py`: 标题生成和标签系统
- `video_clipping.py`: RESTful API接口

### 扩展开发

1. **自定义Gemini配置**
```python
# 在gemini_client.py中自定义生成参数
generation_config = {
    "temperature": 0.5,
    "top_p": 0.9,
    "top_k": 50,
    "max_output_tokens": 4096,
}
```

2. **添加新的质量检测指标**
```python
# 在validator.py中添加新的检测方法
def _validate_custom_metric(self, clip_result: Dict) -> float:
    # 自定义质量检测逻辑
    return score
```

2. **支持新的视频格式**
```python
# 在video_cutter.py中扩展格式支持
SUPPORTED_FORMATS = ['mp4', 'avi', 'mov', 'mkv', 'webm']
```

3. **添加新的标题风格**
```python
# 在title_tagger.py中添加模板
new_templates = [
    "震撼！{topic}的真相",
    "不看后悔：{keyword}的秘密"
]
```

## 📈 性能优化

### 并发处理
- 支持多任务并发处理
- 后台任务异步执行
- 智能资源管理

### 缓存机制
- AI分析结果缓存
- 视频信息缓存
- 中间结果持久化

### 内存管理
- 流式文件处理
- 及时清理临时文件
- 内存使用监控

## 🛡️ 安全考虑

- 文件类型验证
- 文件大小限制
- 路径遍历防护
- API访问限制
- 敏感信息过滤

## 📝 更新日志

### v2.0.0 (2024-01-XX)
- 🔄 **重大更新**: 迁移到Google Gemini 2.5-pro
- 🔐 采用Service Account认证方式
- ⚡ 提升AI分析性能和准确性
- 🛡️ 增强安全性和稳定性
- 📊 优化质量评估算法
- 🌐 完整的RESTful API
- 📖 更新文档和示例

### v1.0.0 (2024-01-XX)
- ✨ 首次发布（基于OpenAI）
- 🎯 完整的AI视频切片功能
- 📊 多维度质量评估系统
- 🏷️ 智能标题标签生成

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

1. Fork本项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 📞 支持与联系

- 📧 邮箱: your-email@example.com
- 🐛 Issue: [GitHub Issues](https://github.com/your-repo/issues)
- 📖 文档: [项目文档](https://your-docs-url.com)
- 💬 讨论: [GitHub Discussions](https://github.com/your-repo/discussions)

---

**⭐ 如果这个项目对你有帮助，请给它一个星标！**