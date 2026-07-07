from __future__ import annotations

from datetime import datetime, timezone

from app.config import settings
from app.schemas import NewsItem


class NewsService:
    """Fetches and normalizes financial news for the engineering workflow."""

    async def fetch_news(
        self,
        query: str,
        tickers: list[str] | None = None,
        limit: int | None = None,
    ) -> list[NewsItem]:
        if settings.news_api_key and settings.news_base_url:
            try:
                from clients.news_client import search_news

                legacy_items = await search_news(
                    query=query,
                    limit=limit or settings.news_page_size,
                    language="en",
                    translate_to_zh=False,
                )
                return [_from_legacy_news(item) for item in legacy_items]
            except Exception:
                return offline_sample_news(query=query, tickers=tickers or [], limit=limit)
        return offline_sample_news(query=query, tickers=tickers or [], limit=limit)


def offline_sample_news(
    query: str = "",
    tickers: list[str] | None = None,
    limit: int | None = None,
) -> list[NewsItem]:
    """Small deterministic fallback so demos and tests run without API keys."""

    now = datetime.now(timezone.utc).isoformat()
    requested = (tickers or ["NVDA", "AAPL", "MSFT"])[:3]
    rows = [
        NewsItem(
            title="Nvidia data center revenue beats estimates as AI chip demand expands",
            summary="Cloud customers increased GPU orders, lifting semiconductor sentiment.",
            url="https://example.com/nvda-ai-demand",
            source="Reuters",
            published_at=now,
            symbol="NVDA",
        ),
        NewsItem(
            title="Federal Reserve signals patience on rate cuts after inflation data",
            summary="Treasury yields moved higher as officials emphasized inflation risk.",
            url="https://example.com/fed-inflation",
            source="CNBC",
            published_at=now,
            symbol="SPY",
        ),
        NewsItem(
            title="Apple suppliers prepare for stronger iPhone production guidance",
            summary="Component makers cited higher production plans for the next quarter.",
            url="https://example.com/apple-suppliers",
            source="MarketWatch",
            published_at=now,
            symbol="AAPL",
        ),
        NewsItem(
            title="Oil prices rise as supply disruption risk grows",
            summary="Energy markets reacted to new geopolitical and shipping risks.",
            url="https://example.com/oil-supply-risk",
            source="Financial Times",
            published_at=now,
            symbol="XOM",
        ),
        NewsItem(
            title="Celebrity movie premiere draws large crowd downtown",
            summary="Entertainment coverage with no clear financial market linkage.",
            url="https://example.com/movie-premiere",
            source="Local News",
            published_at=now,
            symbol=None,
        ),
    ]
    if query or requested:
        preferred = {ticker.upper() for ticker in requested}
        rows.sort(key=lambda item: 0 if (item.symbol or "").upper() in preferred else 1)
    return rows[: limit or settings.news_page_size]


def _from_legacy_news(item) -> NewsItem:
    tickers = list(getattr(item, "matched_tickers", []) or [])
    return NewsItem(
        title=getattr(item, "title", "") or "",
        summary=getattr(item, "content", "") or "",
        url=getattr(item, "url", "") or "",
        source=getattr(item, "source", "") or "",
        published_at=getattr(item, "published_at", "") or "",
        symbol=tickers[0] if tickers else None,
    )

