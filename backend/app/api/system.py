"""Public configuration status (booleans and model names only - never secrets)."""
from fastapi import APIRouter

from ..core.config import get_settings
from ..core.database import get_db
from ..services.audio_extractor import ffmpeg_available

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
async def status():
    s = get_settings()
    db_ok = True
    try:
        await get_db().command("ping")
    except Exception:
        db_ok = False
    provider = s.effective_transcription_provider
    return {
        "app": s.app_name,
        "ai_enabled": s.ai_enabled,
        "demo_mode": not s.ai_enabled,
        "chat_model": s.openai_chat_model if s.ai_enabled else None,
        "embedding_model": s.openai_embedding_model if s.ai_enabled else None,
        "custom_ai_endpoint": bool(s.openai_base_url),
        "transcription_provider": provider,
        "transcription_model": s.openai_transcription_model if provider == "openai" else f"faster-whisper {s.whisper_model}",
        "ffmpeg_available": ffmpeg_available(),
        "database_ok": db_ok,
        "max_upload_mb": s.max_upload_mb,
        "data_disclosure": (
            ("Transcripts are sent to the configured AI provider (OpenAI by default) to generate summaries, notes, "
             "quizzes, flashcards, knowledge maps, chat answers and embeddings."
             + (" Transcript text is also sent to OpenAI moderation for the harsh-language check." if s.moderation_enabled else "")
             + (" Audio is sent to OpenAI for transcription." if provider == "openai" else
                " Audio is transcribed locally on this server and is not sent anywhere."))
            if s.ai_enabled else
            "Demo mode: no AI provider is configured. Audio is transcribed locally and nothing leaves this server."
        ),
    }


@router.get("/health")
async def health():
    return {"ok": True}
