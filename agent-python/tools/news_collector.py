from schemas.news import NewsItem
from tools.news_search import search_news


async def collect_latest_market_news(
    limit: int = 20,
    language: str = "en",
    translate_to_zh: bool = True,
) -> list[NewsItem]:
    """Collect the latest broad market news without user-entered keywords."""
    items = await search_news(
        query="",
        limit=limit,
        language=language,
        translate_to_zh=translate_to_zh,
    )
    return _dedupe_news(items)


def _dedupe_news(items: list[NewsItem]) -> list[NewsItem]:
    seen_urls = set()
    seen_titles = set()
    result: list[NewsItem] = []

    for item in items:
        url_key = item.url.strip().lower()
        title_key = item.title.strip().lower()

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
