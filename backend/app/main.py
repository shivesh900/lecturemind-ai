"""LectureMind AI - FastAPI application entry point.

Run (from backend/):  uvicorn app.main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    install_error_handlers(app)
    for r in (auth, users, lectures, transcript, ai, safety, exports, dashboard, search, system):
        app.include_router(r.router)
    return app


app = create_app()
