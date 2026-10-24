"""Application settings, read from environment variables / .env.

Secrets (OPENAI_API_KEY, JWT_SECRET) live only on the server. Nothing in this
module is ever serialized to the browser; /api/system/status only reports
booleans such as "ai_enabled".
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(BACKEND_DIR.parent / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- app ---
    app_name: str = "LectureMind AI"
    environment: Literal["development", "production", "test"] = "development"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_level: str = "INFO"

    # --- database ---
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "lecturemind"

    # --- auth ---
    jwt_secret: str = "change-me-in-production-please-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24 * 7
    cookie_name: str = "lm_session"
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    # --- storage ---
    storage_dir: str = str(BACKEND_DIR / "storage")
    max_upload_mb: int = 500
    keep_original_upload: bool = True

    # --- transcription ---
    transcription_provider: Literal["auto", "local", "openai"] = "auto"
    whisper_model: str = "base"  # tiny | base | small | medium | large-v3
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    openai_transcription_model: str = "whisper-1"

    # --- OpenAI (LLM + embeddings) ---
    openai_api_key: str = ""
    openai_base_url: str = ""  # optional: any OpenAI-compatible endpoint
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_timeout_seconds: float = 120.0
    openai_max_retries: int = 4
    llm_max_output_tokens: int = 4000
    llm_temperature: float = 0.2
    chunk_target_chars: int = 3500  # ~900 tokens per map-step chunk
    chunk_overlap_segments: int = 1

    # --- jobs / limits ---
    worker_concurrency: int = 1
    job_max_attempts: int = 3
    job_retry_base_seconds: float = 5.0
    ai_rate_limit_per_minute: int = 12
    auth_rate_limit_per_minute: int = 20
    demo_mode_without_key: bool = True

    @property
    def ai_enabled(self) -> bool:
        return bool(self.openai_api_key.strip())

    @property
    def effective_transcription_provider(self) -> str:
        if self.transcription_provider == "auto":
            return "openai" if self.ai_enabled and not self.openai_base_url else "local"
        return self.transcription_provider

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
