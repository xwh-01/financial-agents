# Legacy compatibility module. New code should use clients.news_client.

from clients.news_client import collect_latest_market_news, search_news

__all__ = ["collect_latest_market_news", "search_news"]
