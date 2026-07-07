import math
from datetime import datetime, timezone

from app.config import settings
from app.errors import ExternalServiceError, ExternalServiceNotConfigured
from clients.llm_client import chat_completion
from clients.retry import get_json_with_retry
from market_pulse.schemas import NewsItem


DEFAULT_MARKETAUX_QUERIES = [
    "stock market today major news",
    "global financial markets today",
    "market movers today stocks",
    "stocks moving on news today",
    "Federal Reserve interest rates market impact",
    "inflation data stock market impact",
    "US treasury yields dollar stock market",
    "jobs report unemployment stock market",
    "gold price market impact",
    "oil price energy market impact",
    "commodity prices inflation market impact",
    "geopolitical risk stock market impact",
    "government regulation stock market impact",
    "tariffs trade war market impact",
    "bank stocks market news",
    "energy stocks market news",
    "healthcare stocks market news",
    "retail consumer stocks market news",
    "semiconductor stocks market news",
    "real estate stocks interest rates",
]


async def translate_to_chinese(text: str) -> str:
    if not text.strip():
        return ""

    system_prompt = "You are a professional financial news translator."
    user_prompt = (
        "Translate the following financial news text into concise Simplified Chinese. "
        "Keep company names and stock tickers unchanged.\n\n"
        f"{text}"
    )
    return await chat_completion(system_prompt, user_prompt)


async def search_marketaux_news(
    query: str = "",
    limit: int = 5,
    language: str = "en",
    translate_to_zh: bool = True,
) -> list[NewsItem]:
    if not settings.marketaux_api_key:
        raise ExternalServiceNotConfigured("MARKETAUX_API_KEY is not configured.")

    if not settings.marketaux_base_url:
        raise ExternalServiceNotConfigured("MARKETAUX_BASE_URL is not configured.")

    params = _build_marketaux_params(query=query, limit=limit, language=language)

    try:
        data = await get_json_with_retry(
            settings.marketaux_base_url,
            params=params,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_retry_attempts,
            backoff_seconds=settings.llm_retry_backoff_seconds,
            error_type="marketaux_failed",
        )
        if "error" in data or data.get("status") == "error":
            raise ExternalServiceError(f"Marketaux error: {data}")

        return await _parse_marketaux_response(data=data, translate_to_zh=translate_to_zh)

    except ExternalServiceError:
        raise
    except Exception as exc:
        raise ExternalServiceError(f"Marketaux request failed: {exc}") from exc


async def collect_latest_marketaux_news(
    limit: int = 80,
    language: str = "en",
    translate_to_zh: bool = True,
) -> list[NewsItem]:
    """
    Build a candidate pool from Marketaux finance-related search queries.

    limit means candidate pool size, not final analysis size.
    """
    per_query_limit = max(5, math.ceil(limit / len(DEFAULT_MARKETAUX_QUERIES)))
    all_items: list[NewsItem] = []

    for query in DEFAULT_MARKETAUX_QUERIES:
        try:
            items = await search_marketaux_news(
                query=query,
                limit=per_query_limit,
                language=language,
                translate_to_zh=translate_to_zh,
            )
            all_items.extend(items)
        except Exception as exc:
            print(f"[marketaux] query failed query={query!r}: {exc}")
            if _is_terminal_marketaux_error(exc):
                break

    return _dedupe_news(all_items)


def _is_terminal_marketaux_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "status=401" in message
        or "status=402" in message
        or "usage_limit" in message
        or "usage limit" in message
    )


def _build_marketaux_params(
    query: str,
    limit: int,
    language: str,
) -> dict[str, str | int]:
    params: dict[str, str | int] = {
        "api_token": settings.marketaux_api_key,
        "limit": max(1, min(limit, 50)),
        "language": language,
    }
    clean_query = query.strip()
    if clean_query:
        params["search"] = clean_query
    return params


async def _parse_marketaux_response(
    data: dict,
    translate_to_zh: bool,
) -> list[NewsItem]:
    articles = data.get("data")
    if not isinstance(articles, list):
        return []

    items: list[NewsItem] = []
    for idx, article in enumerate(articles):
        if not isinstance(article, dict):
            continue

        title = article.get("title") or ""
        description = article.get("description") or ""
        snippet = article.get("snippet") or ""
        url = article.get("url") or ""
        published_at = article.get("published_at") or ""
        source = article.get("source") or ""

        item = await _build_news_item(
            idx=idx,
            title=title,
            content=description or snippet,
            source=source,
            url=url,
            published_at=published_at,
            translate_to_zh=translate_to_zh,
        )
        if item:
            items.append(item)

    return items


async def _build_news_item(
    idx: int,
    title: str,
    content: str,
    source: str,
    url: str,
    published_at: str,
    translate_to_zh: bool,
) -> NewsItem | None:
    if not title and not content:
        return None

    title_zh = ""
    content_zh = ""

    if translate_to_zh:
        try:
            title_zh = await translate_to_chinese(title)
        except Exception:
            title_zh = ""

        try:
            content_zh = await translate_to_chinese(content)
        except Exception:
            content_zh = ""

    return NewsItem(
        index=idx,
        title=title,
        title_zh=title_zh,
        content=content,
        content_zh=content_zh,
        source=source,
        url=url,
        published_at=published_at,
        fetched_at=_utc_now_iso(),
        provider="marketaux",
    )


def _dedupe_news(items: list[NewsItem]) -> list[NewsItem]:
    seen_urls = set()
    seen_titles = set()
    result: list[NewsItem] = []

    for item in items:
        url_key = (item.url or "").strip().lower()
        title_key = (item.title or "").strip().lower()

        if url_key and url_key in seen_urls:
            continue

        if title_key and title_key in seen_titles:
            continue

        if url_key:
            seen_urls.add(url_key)

        if title_key:
            seen_titles.add(title_key)

        result.append(item)

    return result


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
