from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from backend.config import Settings
from backend.models.store import LLMModelRecord
from backend.services.crypto import decrypt_secret


@dataclass
class ResolvedModel:
    provider: str
    model_id: str
    kind: str
    api_key: str
    base_url: str


def resolve_model(
    record: Optional[LLMModelRecord],
    kind: str,
    settings: Settings,
) -> Optional[ResolvedModel]:
    """Prefer DB model; fall back to env OpenAI settings for chat/embedding."""
    if record is not None:
        api_key = decrypt_secret(record.api_key_encrypted, settings.app_secret)
        if record.provider == "openai":
            base = record.base_url or settings.openai_base_url
        elif record.provider == "anthropic":
            base = record.base_url or "https://api.anthropic.com"
        else:
            base = record.base_url or ""
        return ResolvedModel(
            provider=record.provider,
            model_id=record.model_id,
            kind=record.kind,
            api_key=api_key,
            base_url=base.rstrip("/"),
        )

    if kind == "chat" and settings.openai_api_key:
        return ResolvedModel(
            provider="openai",
            model_id=settings.openai_model,
            kind="chat",
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url.rstrip("/"),
        )
    if kind == "embedding" and settings.openai_api_key:
        return ResolvedModel(
            provider="openai",
            model_id=settings.embedding_model,
            kind="embedding",
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url.rstrip("/"),
        )
    return None


async def chat_completion(
    model: ResolvedModel,
    system_prompt: str,
    user_prompt: str,
) -> str:
    if model.provider == "openai":
        return await _openai_chat(model, system_prompt, user_prompt)
    if model.provider == "anthropic":
        return await _anthropic_chat(model, system_prompt, user_prompt)
    raise ValueError(f"Unsupported chat provider: {model.provider}")


async def create_embeddings(model: ResolvedModel, texts: list[str]) -> list[list[float]]:
    if model.provider != "openai":
        raise ValueError("Only OpenAI-compatible providers support embeddings in this release")
    headers = {
        "Authorization": f"Bearer {model.api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": model.model_id, "input": texts}
    async with httpx.AsyncClient(base_url=model.base_url, timeout=60.0) as client:
        response = await client.post("/embeddings", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()["data"]
        data_sorted = sorted(data, key=lambda d: d["index"])
        return [item["embedding"] for item in data_sorted]


async def _openai_chat(model: ResolvedModel, system_prompt: str, user_prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {model.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model.model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }
    async with httpx.AsyncClient(base_url=model.base_url, timeout=90.0) as client:
        response = await client.post("/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()


async def _anthropic_chat(model: ResolvedModel, system_prompt: str, user_prompt: str) -> str:
    headers = {
        "x-api-key": model.api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model.model_id,
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    async with httpx.AsyncClient(base_url=model.base_url, timeout=90.0) as client:
        response = await client.post("/v1/messages", headers=headers, json=payload)
        response.raise_for_status()
        blocks = response.json().get("content", [])
        texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
        return "\n".join(texts).strip()
