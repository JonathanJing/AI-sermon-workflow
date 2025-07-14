# Sermon Workflow - Phase 1: Speech-to-Text Service

Automated sermon content workflow system that converts video/audio sermons into high-quality Simplified Chinese subtitles using Google Cloud Speech-to-Text.

## 🎯 Features

- **Multi-source ingestion**: YouTube URLs and local audio/video files
- **Google Cloud STT**: High-accuracy Simplified Chinese transcription
- **Subtitle generation**: SRT and WebVTT formats with proper line wrapping
- **REST API**: RESTful endpoints for job management
- **Batch processing**: CLI tool for processing multiple files
- **Storage options**: Local filesystem or Google Cloud Storage
- **Docker support**: Containerized deployment
- **Cost monitoring**: STT cost estimation and limits

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   YouTube URL   │    │   Local Files   │    │   File Upload   │
│                 │    │                 │    │                 │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼───────────────┐
                    │     FastAPI Service         │
                    │                             │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │   Background Workers        │
                    │                             │
                    └─────────────┬───────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
    ┌─────────▼──────────┐ ┌─────▼──────┐ ┌─────────▼──────────┐
    │   YouTube          │ │   Audio    │ │   Google Cloud      │
    │   Downloader       │ │   Processor│ │   Speech-to-Text   │
    └─────────┬──────────┘ └─────┬──────┘ └─────────┬──────────┘
              │                  │                  │
              └──────────────────┼──────────────────┘
                                 │
                    ┌─────────────▼───────────────┐
                    │   Subtitle Builder          │
                    │                             │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │   Storage Manager           │
                    │   (Local / Google Cloud)    │
                    └─────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- FFmpeg
- Google Cloud credentials (for STT)
- Docker (optional)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd sermon-workflow
   ```

2. **Install dependencies**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.template .env
   # Edit .env with your configuration
   ```

4. **Set up Google Cloud credentials**
   - Create a service account in Google Cloud Console
   - Download the JSON key file
   - Set `GOOGLE_APPLICATION_CREDENTIALS` in `.env`

### Running the Service

**Local development:**
```bash
uvicorn app.main:app --reload
```

**Docker:**
```bash
docker-compose up --build
```

**Production:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 📋 API Usage

### 1. Create Transcription Job

**From YouTube URL:**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "youtube",
    "url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "title": "Sunday Sermon"
  }'
```

**From local file:**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "file",
    "file_path": "/path/to/audio.mp3",
    "title": "Wednesday Service"
  }'
```

**File upload:**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs/transcribe/upload" \
  -F "file=@sermon.mp3" \
  -F "title=Sunday Sermon"
```

### 2. Check Job Status

```bash
curl "http://localhost:8000/api/v1/jobs/{job_id}"
```

### 3. List Jobs

```bash
curl "http://localhost:8000/api/v1/jobs/?limit=10&offset=0"
```

### 4. Health Check

```bash
curl "http://localhost:8000/health"
```

## 🔧 Batch Processing

Use the CLI tool for processing multiple files:

1. **Create CSV input file:**
   ```csv
   source_type,source,title
   youtube,https://www.youtube.com/watch?v=VIDEO1,Sunday Sermon 1
   file,/path/to/audio1.mp3,Wednesday Service 1
   file,/path/to/audio2.mp3,Friday Prayer
   ```

2. **Run batch processing:**
   ```bash
   python scripts/batch_transcribe.py input.csv
   ```

3. **Options:**
   ```bash
   python scripts/batch_transcribe.py input.csv \
     --output results.csv \
     --concurrent-jobs 5 \
     --timeout 7200
   ```

## ⚙️ Configuration

Key configuration options in `.env`:

```env
# Google Cloud
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
GOOGLE_CLOUD_PROJECT=your-project-id
GCS_BUCKET_NAME=your-bucket-name

# Speech-to-Text
STT_LANGUAGE_CODE=cmn-Hans-CN
STT_MODEL=video
STT_COST_LIMIT_USD=10.0

# Storage
STORAGE_TYPE=local  # or 'gcs'
LOCAL_STORAGE_PATH=./data/processed

# API
API_HOST=0.0.0.0
API_PORT=8000
API_KEY=your-api-key
```

## 📁 Project Structure

```
sermon-workflow/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Configuration management
│   ├── models.py               # Data models
│   ├── workers.py              # Background job processing
│   ├── routers/
│   │   └── jobs.py             # API routes
│   └── services/
│       ├── ingest/
│       │   ├── downloader.py   # YouTube downloader
│       │   └── audio_extractor.py  # Audio processing
│       ├── stt/
│       │   └── google_stt.py   # Google Cloud STT
│       ├── subtitles/
│       │   └── builder.py      # Subtitle generation
│       └── storage.py          # Storage management
├── scripts/
│   └── batch_transcribe.py     # Batch processing CLI
├── data/
│   ├── raw/                    # Raw audio files
│   └── processed/              # Processed outputs
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.template
```

## 🔍 Testing

**Run the development server:**
```bash
uvicorn app.main:app --reload
```

**Test with sample YouTube video:**
```bash
curl -X POST "http://localhost:8000/api/v1/jobs/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "youtube",
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "title": "Test Video"
  }'
```

**Check job status:**
```bash
curl "http://localhost:8000/api/v1/jobs/{job_id}"
```

## 📊 Monitoring

- **Health endpoint**: `GET /health`
- **Statistics**: `GET /stats`
- **Configuration**: `GET /config` (debug mode only)
- **Logs**: Structured JSON logging with configurable levels

## 🐳 Docker Deployment

**Development:**
```bash
docker-compose up --build
```

**Production:**
```bash
docker-compose -f docker-compose.yml up -d
```

**With admin interface:**
```bash
docker-compose --profile admin up -d
```

## 🔐 Security

- API key authentication (optional)
- File upload validation
- Resource limits (file size, processing time)
- Cost limits for STT usage
- Non-root container execution

## 📈 Performance & Scaling

- **Concurrent processing**: Background tasks with configurable limits
- **File streaming**: Efficient handling of large audio files
- **Storage optimization**: Automatic cleanup and lifecycle management
- **Cost monitoring**: Real-time STT cost estimation and limits

## 🚧 Known Limitations

1. **Database**: Currently uses in-memory storage (SQLite/PostgreSQL integration planned)
2. **Task queue**: Simple background tasks (Redis/RQ integration available)
3. **Authentication**: Basic API key auth (OAuth2 planned for production)
4. **Monitoring**: Basic health checks (Prometheus metrics available)

## 🛣️ Roadmap

- **Phase 2**: Video clipping and highlight extraction
- **Phase 3**: Devotional content generation with LLM
- **Phase 4**: Multi-platform content distribution
- **Database**: PostgreSQL integration
- **Queue**: Redis/RQ for robust job processing
- **Monitoring**: Prometheus + Grafana dashboard

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
- Check the logs: `docker-compose logs`
- Health check: `curl http://localhost:8000/health`
- Documentation: `http://localhost:8000/docs`

## 📋 Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service account key | Required |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | Required |
| `GCS_BUCKET_NAME` | GCS bucket for file storage | Optional |
| `STT_LANGUAGE_CODE` | Speech-to-Text language | `cmn-Hans-CN` |
| `STT_MODEL` | STT model type | `video` |
| `STT_COST_LIMIT_USD` | Maximum STT cost per job | `10.0` |
| `STORAGE_TYPE` | Storage backend (`local` or `gcs`) | `local` |
| `LOCAL_STORAGE_PATH` | Local storage directory | `./data/processed` |
| `API_HOST` | API server host | `0.0.0.0` |
| `API_PORT` | API server port | `8000` |
| `API_KEY` | API authentication key | Optional |
| `DEBUG` | Enable debug mode | `true` |
| `LOG_LEVEL` | Logging level | `INFO` |
