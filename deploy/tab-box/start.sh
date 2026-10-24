#!/usr/bin/env bash
# LectureMind AI — single-process server (FastAPI API + built React app), Tab-hosted box.
set -u
cd "$(dirname "$0")"
mkdir -p storage
LOG="$PWD/storage/server.log"
# the box has ~470 MB RAM and no swap; Whisper needs more headroom, so add a swap file once
if ! swapon --show 2>/dev/null | grep -q /swapfile; then
  (sudo -n test -f /swapfile || (sudo -n fallocate -l 3G /swapfile && sudo -n chmod 600 /swapfile && sudo -n mkswap /swapfile)) >>"$LOG" 2>&1
  sudo -n swapon /swapfile >>"$LOG" 2>&1 || echo "WARN: swapon failed" >>"$LOG"
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  (sudo -n apt-get update -qq && sudo -n DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ffmpeg) >>"$LOG" 2>&1 || echo "WARN: ffmpeg install failed" >>"$LOG"
fi
if [ ! -x .venv/bin/uvicorn ]; then
  python3 -m venv .venv && .venv/bin/pip install -q --no-cache-dir -r requirements.txt >>"$LOG" 2>&1
fi
set -a; . ./.env; set +a
export HF_HOME="$PWD/.hf-cache" FRONTEND_DIST="$PWD/frontend_dist" STORAGE_DIR="$PWD/storage" ALLOW_FRAMING=1
# keep the server up: restart it if it ever exits
while true; do
  echo "=== start $(date -u +%FT%TZ) ===" >>"$LOG"; free -m >>"$LOG" 2>&1; nproc >>"$LOG"; df -h / >>"$LOG"
  .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips '*' >>"$LOG" 2>&1
  echo "=== exited $? at $(date -u +%FT%TZ) ===" >>"$LOG"; (sudo -n dmesg 2>/dev/null | tail -5) >>"$LOG"
  sleep 2
done
