# Audio Chunking Tests

This directory contains tests for the chunked audio extraction functionality from YouTube videos.

## Test Files

### `test_chunked_extraction.py`

A comprehensive test script that demonstrates the complete workflow for extracting chunked WAV files from YouTube videos.

**Features:**
- Downloads audio from YouTube URL
- Processes audio for optimal STT (Speech-to-Text) performance
- Splits audio into chunks if needed (default: 9MB max per chunk)
- Validates all generated chunk files
- Provides detailed logging and metadata
- Preserves WAV files by default (only cleans up temporary files)

**Usage:**
```bash
# Run full extraction test
python tests/test_chunked_extraction.py

# Only get video info (no download)
python tests/test_chunked_extraction.py --info-only

# Keep all files after completion
python tests/test_chunked_extraction.py --no-cleanup

# Delete all files including WAV files
python tests/test_chunked_extraction.py --full-cleanup
```

**Test URL:** https://youtu.be/QBiaM7BXsY4

## Scripts

### `scripts/extract_chunked_audio.py`

A production-ready script for extracting chunked WAV files from YouTube videos.

**Features:**
- Supports custom job IDs and chunk sizes
- Configurable output directories
- Info-only mode for video metadata
- Verbose logging option
- Error handling and cleanup

**Usage:**
```bash
# Basic extraction
python scripts/extract_chunked_audio.py --url https://youtu.be/QBiaM7BXsY4

# Custom job ID and chunk size
python scripts/extract_chunked_audio.py --url https://youtu.be/QBiaM7BXsY4 --job-id sermon-2024 --chunk-size 5.0

# Extract to specific directory
python scripts/extract_chunked_audio.py --url https://youtu.be/QBiaM7BXsY4 --output-dir ./output

# Get video info only
python scripts/extract_chunked_audio.py --url https://youtu.be/QBiaM7BXsY4 --info-only

# Verbose logging
python scripts/extract_chunked_audio.py --url https://youtu.be/QBiaM7BXsY4 --verbose
```

## Technical Details

### Audio Processing Pipeline

1. **Download**: YouTube audio is downloaded using `yt-dlp` in the best available audio format
2. **Extraction**: Audio is loaded and processed using `pydub` and `ffmpeg`
3. **Optimization**: Audio is optimized for STT:
   - Converted to mono if stereo
   - Preserves original sample rate (8kHz-48kHz supported by Google STT)
   - Only resamples if below 16kHz (for quality) or above 48kHz (Google limit)
   - Normalized audio levels
   - Set to 16-bit sample width
   - Aggressive noise reduction disabled to preserve duration
4. **Chunking**: Large audio files are split into chunks:
   - Default max chunk size: 9MB (under Google STT 10MB limit)
   - Minimum chunk duration: 30 seconds
   - Chunks are numbered sequentially
   - Each chunk is individually optimized

### File Structure

Generated files follow this pattern:
```
data/
├── raw/
│   └── {job_id}_audio.{ext}           # Original downloaded audio
└── processed/
    ├── {job_id}_processed.wav         # Single processed file (if no chunking)
    ├── {job_id}_chunk_000.wav         # First chunk (if chunking needed)
    ├── {job_id}_chunk_001.wav         # Second chunk
    └── ...
```

### Configuration

The system uses the following key configuration values:

- **Max file size**: 500MB (configurable in `app/config.py`)
- **Max chunk size**: 9MB (stays under Google STT 10MB limit)
- **Sample rate**: Preserves original (typically 48kHz for YouTube audio)
- **Audio format**: 16-bit PCM WAV
- **Channels**: Mono (converted from stereo if needed)

## Requirements

- Python 3.8+
- All dependencies from `requirements.txt`
- `ffmpeg` installed on system
- Valid YouTube URL for testing

## Error Handling

The tests include comprehensive error handling for:
- Invalid YouTube URLs
- Network connectivity issues
- Audio processing failures
- File system errors
- Missing dependencies

## Performance

Processing times depend on:
- Video duration
- Internet connection speed
- System resources
- Audio complexity

Example performance for a 45-minute video:
- Download: ~30 seconds
- Processing: ~10 seconds
- Chunking: ~5 seconds
- Total: ~45 seconds

## Troubleshooting

**Common Issues:**

1. **SSL Certificate Error**: The code includes SSL workaround for macOS
2. **ffmpeg Not Found**: Install ffmpeg: `brew install ffmpeg` (macOS) or `apt-get install ffmpeg` (Ubuntu)
3. **Permission Errors**: Ensure write permissions to output directory
4. **YouTube URL Changes**: Some URLs may require updating if YouTube changes their format

**Debug Mode:**
```bash
# Enable debug logging
python scripts/extract_chunked_audio.py --url https://youtu.be/QBiaM7BXsY4 --verbose
```