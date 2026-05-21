# Legacy compatibility module. New code should use clients.news_client.

from clients.news_client import DEFAULT_MARKET_QUERIES, collect_latest_market_news

__all__ = ["DEFAULT_MARKET_QUERIES", "collect_latest_market_news"]
