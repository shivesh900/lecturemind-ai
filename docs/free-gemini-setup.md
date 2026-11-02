# Free AI setup with Google Gemini (no billing)

LectureMind talks to any OpenAI-compatible endpoint, so a free Google AI Studio key works out of the box.

1. Create a key at https://aistudio.google.com/apikey (free tier, no card needed).
2. In `.env`:

```
OPENAI_API_KEY=<your Gemini API key>
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
OPENAI_CHAT_MODEL=gemini-3.5-flash-lite      # free tier: 15 requests/min, 500/day
OPENAI_EMBEDDING_MODEL=gemini-embedding-001  # free tier: 100 requests/min, 1,000/day
OPENAI_EMBEDDING_DIMENSIONS=768              # optional, smaller vectors in MongoDB
OPENAI_MAX_RETRIES=6                         # rides out per-minute 429s
MODERATION_ENABLED=false                     # Gemini has no moderation endpoint; the local Safety lexicon still runs
TRANSCRIPTION_PROVIDER=local                 # faster-whisper on the server, audio never leaves it
```

Notes
- Gemini's embeddings response omits `index`; the client falls back to response order.
- `gemini-2.5-flash` also works but its free tier is only 5 requests/min and 20/day, too low for the full pipeline.
- One short lecture uses roughly 6 chat requests (summary, notes, knowledge map, quiz, flashcards) plus 1 per chat question.
