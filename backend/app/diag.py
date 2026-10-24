"""Operator diagnostics (log tail + memory), guarded by a secret key in DIAG_KEY."""
import os, subprocess
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

router = APIRouter()


@router.get("/api/_diag", include_in_schema=False)
async def diag(k: str = ""):
    key = os.getenv("DIAG_KEY", "")
    if not key or k != key:
        raise HTTPException(status_code=404, detail="Not found")
    log = os.path.join(os.getenv("STORAGE_DIR", "storage"), "server.log")
    tail = subprocess.run(["tail", "-n", "80", log], capture_output=True, text=True).stdout
    mem = subprocess.run(["free", "-m"], capture_output=True, text=True).stdout
    return PlainTextResponse(mem + "\n" + tail)
