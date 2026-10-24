FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Optional: bake the local Whisper model into the image (otherwise it downloads on first use)
ARG PRELOAD_WHISPER=""
RUN if [ -n "$PRELOAD_WHISPER" ]; then python -c "from faster_whisper import WhisperModel; WhisperModel('$PRELOAD_WHISPER', device='cpu', compute_type='int8')"; fi

COPY app ./app
COPY scripts ./scripts
RUN useradd -m lecturemind && mkdir -p /data/storage && chown -R lecturemind /data /app
USER lecturemind
ENV STORAGE_DIR=/data/storage
EXPOSE 8000
# One process: the background job queue runs inside the API process (see README to scale out).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
