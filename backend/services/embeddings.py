from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable, Optional

import httpx
import numpy as np

from backend.config import Settings, get_settings
from backend.services.pdf_parser import PageText


def chunk_pages(
    pages: list[PageText],
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[dict]:
    """Split page text into overlapping character chunks."""
    chunks: list[dict] = []
    for page in pages:
        text = re.sub(r"\s+", " ", page.text).strip()
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            piece = text[start:end].strip()
            if piece:
                chunks.append({"page": page.page, "text": piece})
            if end >= len(text):
                break
            start = max(0, end - chunk_overlap)
    return chunks


def _hash_embed(text: str, dims: int = 256) -> list[float]:
    """Deterministic local embedding fallback when no API key is set."""
    vec = np.zeros(dims, dtype=np.float64)
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    if not tokens:
        tokens = ["empty"]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for i in range(0, min(len(digest), dims)):
            vec[i % dims] += (digest[i] - 128) / 128.0
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec.tolist()
    return (vec / norm).tolist()


async def embed_texts(
    texts: list[str],
    settings: Optional[Settings] = None,
) -> list[list[float]]:
    settings = settings or get_settings()
    if not settings.openai_api_key:
        return [_hash_embed(t) for t in texts]

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": settings.embedding_model, "input": texts}
    async with httpx.AsyncClient(base_url=settings.openai_base_url, timeout=60.0) as client:
        response = await client.post("/embeddings", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()["data"]
        data_sorted = sorted(data, key=lambda d: d["index"])
        return [item["embedding"] for item in data_sorted]


def cosine_similarity(a: Iterable[float], b: Iterable[float]) -> float:
    va = np.asarray(list(a), dtype=np.float64)
    vb = np.asarray(list(b), dtype=np.float64)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def top_k_chunks(
    query_embedding: list[float],
    chunks: list,
    k: int = 5,
    document_ids: Optional[set[str]] = None,
) -> list[tuple[object, float]]:
    scored: list[tuple[object, float]] = []
    for chunk in chunks:
        if document_ids and chunk.document_id not in document_ids:
            continue
        score = cosine_similarity(query_embedding, chunk.embedding)
        scored.append((chunk, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[: max(1, k)]


def ensure_unit(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        return vector
    return [x / norm for x in vector]
