# Multi-stage Dockerfile for FastAPI + Whisper models (pre-baked)
# Stage 1: Pre-download and cache models
FROM python:3.11-slim as model-cache

WORKDIR /tmp/model-download

# Install minimal dependencies for model downloading
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements to install transformers and torch for model download
COPY requirements.txt .
RUN pip install --no-cache-dir --disable-pip-version-check \
    torch==2.10.0 \
    transformers==5.3.0 \
    huggingface_hub \
    pyyaml

# Pre-download Whisper models from Hugging Face Hub
# This runs during image build (not at container startup)
# Use a heredoc to keep the Python script together and avoid linter/parser
# complaints about invalid Dockerfile instructions.
RUN python - <<'PY'
import os
from huggingface_hub import snapshot_download

print('📥 Pre-downloading Whisper models (this may take a few minutes)...')

# Download Kinyarwanda model
print('  - akera/whisper-large-v3-kin-200h-v2...')
snapshot_download(
    repo_id='akera/whisper-large-v3-kin-200h-v2',
    cache_dir='/models_cache',
    force_download=False,
)

# Download English model
print('  - openai/whisper-large-v3...')
snapshot_download(
    repo_id='openai/whisper-large-v3',
    cache_dir='/models_cache',
    force_download=False,
)

print('✅ Models downloaded successfully!')
PY

# Stage 2: Runtime environment
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (librosa, soundfile, etc. need these)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-downloaded models from stage 1
COPY --from=model-cache /models_cache /root/.cache/huggingface/hub

# Copy application code
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

# Set environment variables
ENV DEVICE=cpu
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/root/.cache/huggingface

# Expose port (Fly.io will use $PORT env var)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

# Start Gunicorn + Uvicorn workers
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
