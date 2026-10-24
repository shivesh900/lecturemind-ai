"""LectureMind AI - FastAPI application entry point.

Run (from backend/):  uvicorn app.main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import __version__
from .api import ai, auth, dashboard, exports, lectures, safety, search, system, transcript, users
from .core.config import get_settings
from .core.database import close_db, init_indexes
from .core.errors import install_error_handlers
from .core.logging import setup_logging
from .workers.queue import job_queue

log = logging.getLogger("lecturemind")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    setup_logging(s.log_level)
    if s.environment == "production" and s.jwt_secret.startswith("change-me"):
        raise RuntimeError("Set JWT_SECRET to a long random value in production.")
    if s.environment != "test":
        await init_indexes()
        await job_queue.start()
    log.info("LectureMind AI started (AI %s, transcription=%s)", "enabled" if s.ai_enabled else "DEMO MODE",
             s.effective_transcription_provider)
    yield
    await job_queue.stop()
    await close_db()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="LectureMind AI API", version=__version__, lifespan=lifespan,
                  description="Lecture transcription and knowledge extraction API.")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        if not os.getenv("ALLOW_FRAMING"):  # Hugging Face shows a Space inside an iframe on huggingface.co
            response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    install_error_handlers(app)
    for r in (auth, users, lectures, transcript, ai, safety, exports, dashboard, search, system):
        app.include_router(r.router)
    from . import diag
    app.include_router(diag.router)
    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Single-container deploy (e.g. Hugging Face Spaces): serve the built React app
    from FRONTEND_DIST on the same origin as the API, with an SPA fallback."""
    dist = os.getenv("FRONTEND_DIST", "")
    if not dist or not Path(dist, "index.html").is_file():
        return
    root = Path(dist).resolve()
    index = root / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/") or full_path in ("api", "docs", "redoc", "openapi.json"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (root / full_path).resolve()
        if full_path and candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = create_app()
