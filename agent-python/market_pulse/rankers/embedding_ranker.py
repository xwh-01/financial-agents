"""Layer 2: embedding similarity re-rank. Uses API embeddings to re-rank ~30→~15."""

import logging
import math

import httpx

from app.config import settings
from market_pulse.schemas import NewsItem

logger = logging.getLogger(__name__)

EMBEDDING_LIMIT = 15


async def embedding_rerank(
    items: list[NewsItem],
    query: str,
    limit: int = EMBEDDING_LIMIT,
) -> list[NewsItem]:
    """
    Layer 2 embedding similarity re-rank — cosine similarity between query and
    article title+content embeddings, reducing ~60 candidates to ~40.

    Falls back to truncation (first `limit` items) if:
      - No embedding API key is configured
      - The embedding API call fails
      - The batch response doesn't match input size

    Uses the configured embedding model (default: text-embedding-3-small).
    API key reuses LLM key if no dedicated embedding key is set.
    """
    if not items:
        return []
    if len(items) <= limit:
        return items

    api_key = _embedding_api_key()
    if not api_key:
        logger.info("embedding_rerank: no API key configured, falling back to truncation")
        return items[:limit]

    try:
        query_embedding = await _get_embedding(api_key, query)
        if query_embedding is None:
            logger.warning("embedding_rerank: failed to get query embedding, falling back")
            return items[:limit]

        texts = [_item_text_for_embedding(item) for item in items]
        embeddings = await _get_embeddings_batch(api_key, texts)
        if embeddings is None or len(embeddings) != len(items):
            logger.warning(
                "embedding_rerank: batch embedding mismatch got=%s expected=%s, falling back",
                len(embeddings) if embeddings else 0,
                len(items),
            )
            return items[:limit]

        scored = []
        for i, emb in enumerate(embeddings):
            sim = _cosine_similarity(query_embedding, emb)
            scored.append((items[i], sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in scored[:limit]]

    except Exception:
        logger.warning("embedding_rerank: unexpected error, falling back to truncation", exc_info=True)
        return items[:limit]


def _item_text_for_embedding(item: NewsItem) -> str:
    parts = []
    if item.title:
        parts.append(item.title)
    if item.content:
        parts.append(item.content[:500])
    return " ".join(parts)


def _embedding_api_key() -> str:
    key = (settings.embedding_api_key or "").strip()
    if key:
        return key
    return (settings.llm_api_key or "").strip()


def _embedding_base_url() -> str:
    url = (settings.embedding_base_url or "").strip()
    if url:
        return url
    llm_url = (settings.llm_base_url or "").strip()
    if "/chat/completions" in llm_url:
        return llm_url.replace("/chat/completions", "/embeddings")
    if llm_url:
        return llm_url.rstrip("/") + "/embeddings"
    return "https://api.openai.com/v1/embeddings"


def _embedding_model() -> str:
    return (settings.embedding_model or "text-embedding-3-small").strip()


async def _get_embedding(api_key: str, text: str) -> list[float] | None:
    embeddings = await _get_embeddings_batch(api_key, [text])
    if embeddings and len(embeddings) == 1:
        return embeddings[0]
    return None


async def _get_embeddings_batch(api_key: str, texts: list[str]) -> list[list[float]] | None:
    base_url = _embedding_base_url()
    model = _embedding_model()

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                base_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "input": texts,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in data["data"]]
    except Exception:
        logger.warning("_get_embeddings_batch: request failed", exc_info=True)
        return None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
