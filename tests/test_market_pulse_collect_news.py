import asyncio
from datetime import datetime, timezone

from market_pulse.nodes import collect_news
from market_pulse.schemas import NewsItem


def _news(index: int, source: str = "Reuters", published_at: str | None = None) -> NewsItem:
    return NewsItem(
        title=f"Market news {index}",
        content="Revenue, rates, and market risk context for watchlist analysis.",
        source=source,
        url=f"https://example.com/{index}",
        published_at=published_at or datetime.now(timezone.utc).isoformat(),
    )


def test_build_candidate_pool_caps_at_300_without_freshness_filtering():
    stale = _news(999, published_at="2020-01-01T00:00:00Z")
    items = [stale] + [_news(i) for i in range(350)]

    pool = collect_news.build_candidate_pool(items)

    assert len(pool) == 300
    assert stale not in pool


def test_build_candidate_pool_keeps_stale_items_when_pool_is_under_cap():
    stale = _news(1, published_at="2020-01-01T00:00:00Z")
    fresh = _news(2)

    pool = collect_news.build_candidate_pool([stale, fresh])

    assert pool == [stale, fresh]


def test_collect_news_node_builds_bounded_multi_source_candidate_pool(monkeypatch):
    calls = {}

    async def fake_search_marketaux_news(**kwargs):
        calls["query_limit"] = kwargs["limit"]
        return [_news(i, source="Reuters") for i in range(120)]

    async def fake_collect_company_market_news(**kwargs):
        calls["company_limit"] = kwargs["limit"]
        return [_news(i + 120, source="Bloomberg") for i in range(120)]

    async def fake_collect_fin_rss_news(**kwargs):
        calls["rss_limit"] = kwargs["limit"]
        calls["rss_tickers"] = kwargs["tickers"]
        return [_news(i + 240, source="CNBC") for i in range(120)]

    monkeypatch.setattr(
        collect_news,
        "search_marketaux_news",
        fake_search_marketaux_news,
    )
    monkeypatch.setattr(collect_news.settings, "collect_enable_marketaux", True)
    monkeypatch.setattr(
        collect_news,
        "collect_company_market_news",
        fake_collect_company_market_news,
    )
    monkeypatch.setattr(
        collect_news,
        "collect_fin_rss_news",
        fake_collect_fin_rss_news,
    )

    result = asyncio.run(
        collect_news.collect_news_node(
            {"query": "tickers: NVDA", "tickers": ["NVDA"]}
        )
    )

    assert calls == {
        "query_limit": 100,
        "company_limit": 180,
        "rss_limit": 240,
        "rss_tickers": ["NVDA"],
    }
    assert len(result["candidate_news"]) == 300
