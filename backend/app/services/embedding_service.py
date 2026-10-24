"""Chunk embeddings, stored on the chunk documents as compact float32 binary
(normalised, so cosine similarity is a dot product).

For larger deployments, MongoDB Atlas Vector Search can index the same field
(store as an array instead); see README.
"""
from __future__ import annotations

import numpy as np
from bson.binary import Binary

from ..core.config import get_settings
from .llm_client import get_llm_client


def to_binary(vec: list[float]) -> Binary:
    arr = np.asarray(vec, dtype=np.float32)
    norm = float(np.linalg.norm(arr)) or 1.0
    return Binary((arr / norm).astype(np.float32).tobytes())


def from_binary(b: bytes) -> np.ndarray:
    return np.frombuffer(bytes(b), dtype=np.float32)


async def embed_texts(texts: list[str]) -> list[list[float]]:
    return await get_llm_client().embed(texts)


async def embed_chunks(db, lecture_id, chunks: list[dict]) -> int:
    if not chunks:
        return 0
    vectors = await embed_texts([c["text"] for c in chunks])
    model = get_settings().openai_embedding_model
    for c, v in zip(chunks, vectors):
        await db.transcript_chunks.update_one(
            {"lecture_id": lecture_id, "idx": c["idx"]},
            {"$set": {"embedding": to_binary(v), "embedding_model": model, "embedding_dim": len(v)}},
        )
    return len(vectors)


async def embed_query(text: str) -> np.ndarray:
    v = (await embed_texts([text]))[0]
    return from_binary(to_binary(v))
