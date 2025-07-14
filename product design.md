# **Phase 1 Technical Design –** ****

# **Automated Sermon Content Workflow**

> **Goal:** Build a Python-based service that ingests weekly sermon video/audio and delivers high-quality Simplified-Chinese subtitles using Google Cloud Speech-to-Text (STT). This document captures product design, development requirements, and the proposed file structure for Phase 1.

---

## **1. Business Context & Problem Statement**

* **Low Engagement:** Existing full-length sermons on YouTube attract few views and do not grow channel subscriptions.
* **Retention Gap:** Congregants quickly forget Sunday messages; there is limited devotional content during the week.
* **Manual Bottleneck:** Editing and captioning currently rely on volunteers and are not scalable.

*Phase 1 attacks the highest-impact bottleneck: ****accurate Chinese subtitles****, the foundation for later automated clipping, devotionals, and social distribution.*

---

## **2. Scope – Phase 1 MVP**

| **#** | **Capability**                         | **Must-Have** | **Notes**                                                                         |
| ----------- | -------------------------------------------- | ------------------- | --------------------------------------------------------------------------------------- |
| 1           | **Ingest**YouTube URL or local MP3/MP4 | ✅                  | Download & extract audio (48 kHz preferred)                                             |
| 2           | **Speech-to-Text**(Simplified Chinese) | ✅                  | Google Cloud STT*video*model, enhanced; diarization optional                          |
| 3           | **Subtitle Assembly**                  | ✅                  | Produce SRT & WebVTT with line length ≤ 42 chars                                       |
| 4           | **Storage**                            | ✅                  | Save raw audio, JSON transcript, and subtitle files to**/data/processed/**or GCS bucket |
| 5           | REST**API**endpoint                    | ✅                  | **POST /transcribe**with URL/file and returns download links                      |
| 6           | Basic**CLI**for batch runs             | ✅                  | python -m tools.batch_transcribe input.csv                                              |
| 7           | **Logging & Metrics**                  | ✅                  | Structured logs, processing time, STT cost estimate                                     |
| 8           | Dockerized deployment                        | ✅                  | One-click run on GKE/Cloud Run or on-prem                                               |

Out-of-scope for Phase 1: video clipping, devotional generation, content distribution.

---

## **3. Functional Architecture**

```
graph TD;
  A[Video/Audio Source] -->|Download & Extract| B(Audio File)
  B --> C[Google STT API]
  C --> D{Transcript JSON}
  D --> E[Subtitle Post-Processor]
  E --> F[SRT / VTT Files]
  F --> G[Storage (GCS / Local)]
  G --> H[FastAPI Service]
```

### **3.1 Ingestion Service**

* Tools: **pytube** for YouTube, **ffmpeg**/**moviepy** for audio extraction.
* Validates file duration (<2 h for STT batch limit).

### **3.2 Speech-to-Text Service**

* **Library: **google-cloud-speech>=2.27**.**
* **Config: **language_code="cmn-Hans-CN"**, **model="video"**, **enable_word_time_offsets=True**.**
* Splits audio into ≤ 1-minute chunks if file > 300 MB.

### **3.3 Subtitle Post-Processor**

* Aligns word-level timestamps into readable sentences.
* Handles Chinese punctuation and line wrapping.
* Exports **.srt** and **.vtt** via **pysubs2**.

### **3.4 Storage Layer**

* Default: local **/data/…**; cloud option: GCS bucket with lifecycle rules.

### **3.5 Orchestration & API**

* Framework: **FastAPI** with **uvicorn**.
* One endpoint and a simple queue for async jobs (e.g., **RQ** or **Celery**).

---

## **4. Technical Stack**

| **Layer** | **Choice**                                                                          | **Rationale**                |
| --------------- | ----------------------------------------------------------------------------------------- | ---------------------------------- |
| Language        | **Python 3.11**                                                                     | Rich ecosystem & team skillset     |
| Core Libraries  | google-cloud-speech**,**moviepy**,**pysubs2**,**pydub**,**ffmpeg-python | Battle-tested media handling       |
| API             | **FastAPI**                                                                         | Async-first, OpenAPI docs auto-gen |
| Task Queue      | **redis-rq**(starter)                                                               | Lightweight and easy to operate    |
| Packaging       | **Docker**+docker-compose                                                           | Consistent local ⇄ prod           |
| CI              | GitHub Actions                                                                            | Lint → test → build → push      |

---

## **5. Development Requirements**

### **5.1 Functional Requirements**

1. **Submit Job** – Accept payload { "source_type":"youtube|file", "url_or_path":"..." }**.**
2. **Track Status** – /jobs/{id}** returns JSON: **PENDING|IN_PROGRESS|SUCCEEDED|FAILED**.**
3. **Download Results** – Provide secure pre-signed URLs (GCS or local) for transcript & subtitles.
4. **Accuracy Target** – ≥ 95 % word-accuracy on clear Mandarin audio (baseline church recording).
5. **Cost Control** – Automatic early-exit if projected STT cost > configured cap.

### **5.2 Non-Functional Requirements**

* **Runtime**: Complete 1-hour sermon ≤ 10 min (n1-standard-4, US-West).
* **Observability**: Prometheus metrics, Sentry error reporting.
* **Security**: Google IAM least-privilege, API key auth.
* **Extensibility**: Modular services ready for Phase 2 (summarization).

---

## **6. Local Development Environment**

```
# 1. Clone repo
$ git clone git@github.com:church-media/sermon-workflow.git
$ cd sermon-workflow

# 2. Create virtualenv
$ python -m venv .venv && source .venv/bin/activate

# 3. Install deps
$ pip install -r requirements.txt

# 4. Export creds
$ cp .env.template .env  # add GOOGLE_APPLICATION_CREDENTIALS

# 5. Run dev server
$ uvicorn app.main:app --reload
```

---

## **7. Suggested Repository & File Structure**

```
sermon-workflow/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI entrypoint
│   ├── config.py        # Pydantic settings
│   ├── models.py        # Job ORM (SQLModel)
│   ├── routers/
│   │   └── jobs.py
│   ├── services/
│   │   ├── ingest/
│   │   │   ├── __init__.py
│   │   │   ├── downloader.py
│   │   │   └── audio_extractor.py
│   │   ├── stt/
│   │   │   ├── __init__.py
│   │   │   └── google_stt.py
│   │   ├── subtitles/
│   │   │   ├── __init__.py
│   │   │   └── builder.py
│   │   └── storage.py
│   └── workers.py       # RQ workers
├── data/
│   ├── raw/
│   └── processed/
├── scripts/
│   └── batch_transcribe.py
├── tests/
│   └── test_end_to_end.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
└── .env.template
```

---

## **8. Deployment & CI/CD**

1. **CI Pipeline (GitHub Actions)**
   * Trigger on **main** and PRs
   * Steps: *flake8* → *pytest* → build Docker → push to GCR
2. **CD**: Deploy image to Cloud Run (or GKE) using GitHub Environments.
3. **Secrets** stored in GitHub Secrets & Google Secret Manager.

---

## **9. Roadmap Beyond Phase 1**

| **Phase** | **Key Feature**                       | **Dependency**    |
| --------------- | ------------------------------------------- | ----------------------- |
| 2               | Clip Extraction (15-sec highlights)         | Reliable subtitles (P1) |
| 3               | Devotional & Discussion Material Generation | LLM integration         |
| 4               | Multi-platform Publishing                   | Clip & text assets      |

---

### **Appendix A – Google STT Configuration Snippet**

```
from google.cloud import speech_v1p1beta1 as speech

client = speech.SpeechClient()
config = speech.RecognitionConfig(
    language_code="cmn-Hans-CN",
    model="video",
    enable_word_time_offsets=True,
    enable_automatic_punctuation=True,
)
audio = speech.RecognitionAudio(uri=gcs_uri)
operation = client.long_running_recognize(config=config, audio=audio)
response = operation.result(timeout=3600)
```

---

**Author:** Product & Engineering – July 2025
