from urllib.parse import urlparse

import feedparser
import httpx

from app.config import settings
from schemas.news import NewsItem


async def fetch_rss_feed(url: str, limit: int = 20) -> list[NewsItem]:
    async with httpx.AsyncClient(timeout=settings.rss_timeout_seconds) as client:
        response = await client.get(url)
        response.raise_for_status()

    parsed = feedparser.parse(response.content)
    feed_title = parsed.feed.get("title") if parsed.feed else ""
    source = feed_title or _domain_from_url(url)
    items: list[NewsItem] = []

    for idx, entry in enumerate(parsed.entries[: max(0, limit)]):
        title = _as_text(entry.get("title"))
        content = _as_text(
            entry.get("summary")
            or entry.get("description")
            or entry.get("subtitle")
        )
        link = _as_text(entry.get("link"))
        published_at = _as_text(entry.get("published") or entry.get("updated"))

        if not title and not content:
            continue

        items.append(
            NewsItem(
                index=idx,
                title=title,
                content=content,
                source=source,
                url=link,
                published_at=published_at,
                provider="rss",
            )
        )

    return items


async def fetch_rss_feeds(
    urls: list[str],
    limit_per_feed: int = 20,
) -> list[NewsItem]:
    items: list[NewsItem] = []

    for url in urls:
        try:
            items.extend(await fetch_rss_feed(url, limit=limit_per_feed))
        except Exception as exc:
            print(f"[rss] skip feed url={url}: {exc}")

    return items


def _domain_from_url(url: str) -> str:
    return urlparse(url).netloc or "rss"


def _as_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()
