from schemas.news import NewsItem
from tools.news_search import search_news
import math


DEFAULT_MARKET_QUERIES = [
    "Nvidia AI chips stock",
    "Tesla robotaxi stock",
    "Apple iPhone stock",
    "Microsoft Azure OpenAI stock",
    "Google AI antitrust stock",
    "Amazon AWS stock",
    "semiconductor stocks earnings",
    "Federal Reserve interest rates stock market",
    "gold price inflation Federal Reserve",
    "oil price energy stocks geopolitical risk",
]


async def collect_latest_market_news(
    limit: int = 80,
    language: str = "en",
    translate_to_zh: bool = True,
) -> list[NewsItem]:
    """
    Build a candidate news pool from multiple finance-related queries.

    limit means candidate pool size, not final analysis size.
    """
    per_query_limit = max(3, math.ceil(limit / len(DEFAULT_MARKET_QUERIES)))
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
        except Exception:
            continue

    return _dedupe_news(all_items)


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
