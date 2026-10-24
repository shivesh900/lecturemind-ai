"""Thin async wrapper around the OpenAI SDK.

* Structured JSON output validated with pydantic (`chat_json`). Uses
  response_format=json_schema and falls back to json_object for endpoints that
  do not support schemas. One corrective retry on invalid JSON.
* Transient failures (429 / 5xx / timeouts) are retried by the SDK with
  exponential backoff (OPENAI_MAX_RETRIES), plus one extra outer retry.
* The API key never leaves the server and is never logged.
* `OPENAI_BASE_URL` lets you point at any OpenAI-compatible endpoint.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from ..core.config import get_settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(RuntimeError):
    """No API key configured."""


class LLMError(RuntimeError):
    pass


def _extract_json(text: str) -> str:
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start : end + 1]
    return text


class LLMClient:
    def __init__(self, client=None):
        self._client = client
        self._json_schema_supported = True

    def raw_client(self):
        if self._client is None:
            s = get_settings()
            if not s.ai_enabled:
                raise LLMUnavailable("OPENAI_API_KEY is not configured on the server.")
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=s.openai_api_key,
                base_url=s.openai_base_url or None,
                timeout=s.openai_timeout_seconds,
                max_retries=s.openai_max_retries,
            )
        return self._client

    async def chat_json(self, system: str, user: str, schema: type[T], *, max_tokens: int | None = None,
                        temperature: float | None = None) -> T:
        s = get_settings()
        client = self.raw_client()
        schema_json = schema.model_json_schema()
        sys_prompt = (
            system.strip()
            + "\n\nRespond ONLY with a JSON object that matches this JSON Schema (no prose, no markdown):\n"
            + json.dumps(schema_json, separators=(",", ":"))
        )
        messages = [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user}]
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                content = await self._complete(client, messages, schema, schema_json,
                                               max_tokens or s.llm_max_output_tokens,
                                               s.llm_temperature if temperature is None else temperature)
                return schema.model_validate_json(_extract_json(content))
            except (ValidationError, json.JSONDecodeError, ValueError) as exc:
                last_err = exc
                log.warning("LLM output failed validation for %s (attempt %d)", schema.__name__, attempt + 1)
                messages = messages[:2] + [
                    {"role": "assistant", "content": (content if "content" in locals() else "")[:4000]},
                    {"role": "user", "content": f"That JSON was invalid: {str(exc)[:800]}. Return corrected JSON only."},
                ]
            except LLMUnavailable:
                raise
            except Exception as exc:  # network / API errors after SDK retries
                last_err = exc
                name = type(exc).__name__
                log.warning("LLM call failed (%s), attempt %d", name, attempt + 1)
                if attempt < 2:
                    await asyncio.sleep(2 * (attempt + 1))
        raise LLMError(f"AI generation failed: {type(last_err).__name__}: {str(last_err)[:300]}")

    async def _complete(self, client, messages, schema, schema_json, max_tokens, temperature) -> str:
        s = get_settings()
        kwargs = dict(model=s.openai_chat_model, messages=messages, max_tokens=max_tokens, temperature=temperature)
        if self._json_schema_supported:
            try:
                resp = await client.chat.completions.create(
                    **kwargs,
                    response_format={"type": "json_schema",
                                     "json_schema": {"name": schema.__name__, "schema": schema_json, "strict": False}},
                )
                return resp.choices[0].message.content or ""
            except Exception as exc:
                status = getattr(exc, "status_code", None)
                if status == 400 and "response_format" in str(exc):
                    log.info("Endpoint does not support json_schema; falling back to json_object")
                    self._json_schema_supported = False
                else:
                    raise
        resp = await client.chat.completions.create(**kwargs, response_format={"type": "json_object"})
        return resp.choices[0].message.content or ""

    async def embed(self, texts: list[str], batch_size: int = 64) -> list[list[float]]:
        s = get_settings()
        client = self.raw_client()
        out: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = [t[:8000] if t.strip() else " " for t in texts[i : i + batch_size]]
            resp = await client.embeddings.create(model=s.openai_embedding_model, input=batch)
            out.extend([d.embedding for d in sorted(resp.data, key=lambda d: d.index)])
        return out


_llm: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm


def set_llm_client(client: LLMClient | None) -> None:
    """Tests inject a fake client here."""
    global _llm
    _llm = client
