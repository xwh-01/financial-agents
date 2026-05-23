import math
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.errors import ExternalServiceError, ExternalServiceNotConfigured
from clients.llm_client import chat_completion
from market_pulse.schemas import NewsItem


DEFAULT_MARKET_QUERIES = [
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


async def search_news(
    query: str = "",
    limit: int = 5,
    language: str = "en",
    translate_to_zh: bool = True,
) -> list[NewsItem]:
    if not settings.news_api_key:
        raise ExternalServiceNotConfigured("NEWS_API_KEY is not configured.")

    if not settings.news_base_url:
        raise ExternalServiceNotConfigured("NEWS_BASE_URL is not configured.")

    provider = _detect_news_provider(settings.news_base_url)
    params = _build_news_params(
        provider=provider,
        query=query,
        limit=limit,
        language=language,
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(settings.news_base_url, params=params)

        if resp.status_code >= 400:
            raise ExternalServiceError(
                f"{provider} news request failed: "
                f"status={resp.status_code}, body={resp.text}"
            )

        data = resp.json()
        if "error" in data:
            raise ExternalServiceError(f"{provider} error: {data}")
        if data.get("status") == "error":
            raise ExternalServiceError(f"{provider} error: {data}")

        return await _parse_news_response(
            provider=provider,
            data=data,
            translate_to_zh=translate_to_zh,
        )

    except ExternalServiceError:
        raise
    except Exception as exc:
        raise ExternalServiceError(f"{provider} news request failed: {exc}") from exc


async def collect_latest_market_news(
    limit: int = 80,
    language: str = "en",
    translate_to_zh: bool = True,
) -> list[NewsItem]:
    """
    Build a candidate news pool from multiple finance-related queries.

    limit means candidate pool size, not final analysis size.
    """
    per_query_limit = max(5, math.ceil(limit / len(DEFAULT_MARKET_QUERIES)))
    all_items: list[NewsItem] = []

    for query in DEFAULT_MARKET_QUERIES:
        try:
            items = await search_news(
                query=query,
                limit=per_query_limit,
                language=language,
                translate_to_zh=translate_to_zh,
            )
            all_items.extend(items)
        except Exception as exc:
            print(f"[news-api] query failed query={query!r}: {exc}")
            if _is_terminal_news_error(exc):
                break

    return _dedupe_news(all_items)


def _detect_news_provider(base_url: str) -> str:
    host = urlparse(base_url).netloc.lower()
    if "newsapi.org" in host:
        return "newsapi"
    if "marketaux.com" in host:
        return "marketaux"
    return "generic"


def _is_terminal_news_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "status=401" in message
        or "status=402" in message
        or "apikeyinvalid" in message
        or "usage_limit" in message
        or "usage limit" in message
    )


def _build_news_params(
    provider: str,
    query: str,
    limit: int,
    language: str,
) -> dict[str, str | int]:
    safe_limit = max(1, min(limit, 50))
    clean_query = query.strip()

    if provider == "newsapi":
        params: dict[str, str | int] = {
            "apiKey": settings.news_api_key,
            "pageSize": safe_limit,
            "language": language,
            "sortBy": "publishedAt",
        }
        if clean_query:
            params["q"] = clean_query
        return params

    params = {
        "api_token": settings.news_api_key,
        "limit": safe_limit,
        "language": language,
    }
    if clean_query:
        params["search"] = clean_query
    return params


async def _parse_news_response(
    provider: str,
    data: dict,
    translate_to_zh: bool,
) -> list[NewsItem]:
    articles = data.get("articles") if provider == "newsapi" else data.get("data")
    if not isinstance(articles, list):
        return []

    items: list[NewsItem] = []
    for idx, article in enumerate(articles):
        if not isinstance(article, dict):
            continue

        item = await _parse_article(
            idx=idx,
            provider=provider,
            article=article,
            translate_to_zh=translate_to_zh,
        )
        if item:
            items.append(item)

    return items


async def _parse_article(
    idx: int,
    provider: str,
    article: dict,
    translate_to_zh: bool,
) -> NewsItem | None:
    if provider == "newsapi":
        source_data = article.get("source") or {}
        source = source_data.get("name") if isinstance(source_data, dict) else ""
        title = article.get("title") or ""
        description = article.get("description") or ""
        content = article.get("content") or ""
        url = article.get("url") or ""
        published_at = article.get("publishedAt") or ""

        return await _build_news_item(
            idx=idx,
            title=title,
            content=description or content,
            source=source or "",
            url=url,
            published_at=published_at,
            provider=provider,
            translate_to_zh=translate_to_zh,
        )

    title = article.get("title") or ""
    description = article.get("description") or ""
    snippet = article.get("snippet") or ""
    url = article.get("url") or ""
    published_at = article.get("published_at") or ""
    source = article.get("source") or ""

    return await _build_news_item(
        idx=idx,
        title=title,
        content=description or snippet,
        source=source,
        url=url,
        published_at=published_at,
        provider=provider,
        translate_to_zh=translate_to_zh,
    )


async def _build_news_item(
    idx: int,
    title: str,
    content: str,
    source: str,
    url: str,
    published_at: str,
    provider: str,
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
        provider=provider,
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
