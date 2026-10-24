# Single-container build for Hugging Face Spaces (Docker SDK).
# FastAPI serves the API and the built React app on the same origin, port 7860.
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
# Hugging Face runs the container as uid 1000
RUN useradd -m -u 1000 user
WORKDIR /home/user/app
COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt
# Bake the faster-whisper "base" model into the image so the first upload doesn't wait on a download
ENV HF_HOME=/opt/hf-cache
RUN mkdir -p /opt/hf-cache && python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')" \
    && chown -R user /opt/hf-cache
COPY --chown=user backend/app ./app
COPY --chown=user backend/scripts ./scripts
COPY --from=web --chown=user /web/dist ./frontend_dist
RUN mkdir -p /home/user/app/storage && chown -R user /home/user/app
USER user
ENV FRONTEND_DIST=/home/user/app/frontend_dist \
    STORAGE_DIR=/home/user/app/storage \
    ENVIRONMENT=production \
    WHISPER_MODEL=base WHISPER_DEVICE=cpu WHISPER_COMPUTE_TYPE=int8 \
    COOKIE_SECURE=true COOKIE_SAMESITE=none ALLOW_FRAMING=1 \
    CORS_ORIGINS=https://huggingface.co
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers", "--forwarded-allow-ips", "*"]
