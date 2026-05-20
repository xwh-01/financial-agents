import asyncio
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schemas.news import NewsItem
from tools.company_feed_config import load_company_feeds
from tools.source_aggregator import build_google_news_rss_url, dedupe_news_items


def test_load_company_feeds() -> None:
    configs = load_company_feeds()
    assert len(configs) == 5, f"expected 5 company configs, got {len(configs)}"
    assert {item["ticker"] for item in configs} == {
        "NVDA",
        "AMD",
        "AAPL",
        "MSFT",
        "TSLA",
    }


def test_google_news_rss_url() -> None:
    url = build_google_news_rss_url("NVIDIA AI chips")
    assert url == (
        "https://news.google.com/rss/search?"
        "q=NVIDIA+AI+chips&hl=en-US&gl=US&ceid=US:en"
    )


def test_dedupe_news_items() -> None:
    items = [
        NewsItem(title="NVIDIA earnings", url="https://example.com/a"),
        NewsItem(title="Different title", url="https://example.com/a"),
        NewsItem(title="NVIDIA earnings", url="https://example.com/b"),
        NewsItem(title="AMD AI chips", url="https://example.com/c"),
    ]

    deduped = dedupe_news_items(items)
    assert len(deduped) == 2
    assert [item.title for item in deduped] == ["NVIDIA earnings", "AMD AI chips"]


async def test_single_rss_failure_is_skipped() -> None:
    import tools.rss_collector as rss_collector

    async def fake_fetch_rss_feed(url: str, limit: int = 20):
        if "bad" in url:
            raise RuntimeError("boom")
        return [NewsItem(title="OK", url="https://example.com/ok", provider="rss")]

    original = rss_collector.fetch_rss_feed
    rss_collector.fetch_rss_feed = fake_fetch_rss_feed
    try:
        items = await rss_collector.fetch_rss_feeds(
            ["https://bad.example/rss", "https://good.example/rss"],
            limit_per_feed=5,
        )
    finally:
        rss_collector.fetch_rss_feed = original

    assert len(items) == 1
    assert items[0].title == "OK"


async def main() -> None:
    test_load_company_feeds()
    test_google_news_rss_url()
    test_dedupe_news_items()
    await test_single_rss_failure_is_skipped()
    print("company rss tests passed")


if __name__ == "__main__":
    asyncio.run(main())
