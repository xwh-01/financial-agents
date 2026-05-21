# Legacy compatibility module. New code should use clients.rss_client.

from clients.rss_client import (
    build_google_news_rss_url,
    collect_company_market_news,
    dedupe_news_items,
)

__all__ = [
    "build_google_news_rss_url",
    "collect_company_market_news",
    "dedupe_news_items",
]
