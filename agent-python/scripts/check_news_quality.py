"""Verify news dedupe and freshness filter logic (no API key needed).

Usage:
  python scripts/check_news_quality.py
"""
import sys
from datetime import datetime, timedelta, timezone

from market_pulse.filters.news_filter import dedupe_news, filter_fresh_news
from market_pulse.rankers.source_weight import get_source_weight
from market_pulse.schemas import NewsItem
from market_pulse.utils.news_normalizer import make_content_hash, normalize_title, normalize_url


def _item(title: str, url: str = "", source: str = "", published_at: str = "") -> NewsItem:
    return NewsItem(
        title=title,
        url=url,
        source=source,
        published_at=published_at,
    )


def test_normalize() -> None:
    print("=== normalize_title ===")
    cases = [
        ("NVIDIA Stock Soars on AI Chip Demand!", "nvidia stock soars on ai chip demand"),
        ("  Market  Update   Today ", "market update today"),
        ("Fed Raises Rates -- What It Means", "fed raises rates what it means"),
    ]
    for raw, expected in cases:
        got = normalize_title(raw)
        status = "OK" if got == expected else f"FAIL (expected: {expected!r})"
        print(f"  {raw!r} -> {got!r}  {status}")

    print("\n=== normalize_url ===")
    url_cases = [
        (
            "https://reuters.com/article?id=123&utm_source=twitter&utm_medium=social",
            "https://reuters.com/article?id=123",
        ),
        (
            "https://cnbc.com/news?utm_campaign=daily",
            "https://cnbc.com/news",
        ),
    ]
    for raw, expected in url_cases:
        got = normalize_url(raw)
        status = "OK" if got == expected else f"FAIL (expected: {expected!r})"
        print(f"  {raw} -> {got}  {status}")

    print("\n=== make_content_hash ===")
    h1 = make_content_hash("NVIDIA Chips", "https://reuters.com/nvda")
    h2 = make_content_hash("NVIDIA Chips", "https://reuters.com/nvda")
    h3 = make_content_hash("NVIDIA Chips", "https://cnbc.com/nvda")
    print(f"  same title+url:  {'OK' if h1 == h2 else 'FAIL'}")
    print(f"  different url:  {'OK' if h1 != h3 else 'FAIL'}")


def test_source_weight() -> None:
    print("\n=== get_source_weight ===")
    cases = [
        ("Reuters", "", 1.0),
        ("Bloomberg", "", 1.0),
        ("CNBC", "", 0.9),
        ("Yahoo Finance", "", 0.85),
        ("MarketWatch", "", 0.8),
        ("Google News", "", 0.75),
        ("", "reuters.com", 1.0),
        ("", "bloomberg.com", 1.0),
        ("NVIDIA Investor Relations", "", 0.95),
        ("Some Random Blog", "", 0.5),
        ("", "investor.nvidia.com", 0.95),
        ("Unknown Source", "", 0.5),
    ]
    for source, url, expected in cases:
        got = get_source_weight(source, url)
        status = "OK" if got == expected else f"FAIL (expected: {expected})"
        print(f"  source={source!r} url={url!r} -> {got}  {status}")


def test_dedupe() -> None:
    print("\n=== dedupe_news ===")
    now = datetime.now(timezone.utc).isoformat()

    items = [
        _item("NVIDIA AI chips surge", "https://reuters.com/nvda", "Reuters", now),
        _item("NVIDIA AI chips surge", "https://cnbc.com/nvda", "CNBC", now),
        _item("Gold hits new high", "https://reuters.com/gold", "Reuters", now),
        _item("Gold hits new high !!!", "https://reuters.com/gold", "Reuters", now),
        _item("Oil prices drop", "https://bloomberg.com/oil", "Bloomberg", now),
    ]
    print(f"  input: {len(items)} items")
    kept = dedupe_news(items)
    print(f"  after dedupe: {len(kept)} items (expected: 3)")
    for item in kept:
        sw = get_source_weight(item.source, item.url)
        print(f"    title={item.title[:40]:<40} source={item.source:<12} source_weight={sw}")


def test_freshness() -> None:
    print("\n=== filter_fresh_news ===")
    now = datetime.now(timezone.utc)
    fresh = (now - timedelta(hours=1)).isoformat()
    old3d = (now - timedelta(hours=80)).isoformat()
    old7d = (now - timedelta(days=8)).isoformat()
    no_time = ""

    items = [
        _item("Fresh news 1 hour ago", "https://r1.com", "Reuters", fresh),
        _item("Old news 80 hours ago", "https://r2.com", "Reuters", old3d),
        _item("Very old 8 days ago", "https://r3.com", "Reuters", old7d),
        _item("No timestamp", "https://r4.com", "Reuters", no_time),
    ]
    print(f"  input: {len(items)} items")
    kept = filter_fresh_news(items, max_age_hours=72)
    print(f"  after freshness filter (max 72h): {len(kept)} items (expected: 2)")
    for item in kept:
        print(f"    title={item.title[:40]:<40} published_at={item.published_at[:20]}")


def test_ranking_integration() -> None:
    print("\n=== source_weight in ranking (simulated) ===")
    now = datetime.now(timezone.utc).isoformat()
    items = [
        _item("NVIDIA earnings beat estimates", "https://reuters.com/nvda-earn", "Reuters", now),
        _item("NVIDIA chip demand strong", "https://randomblog.com/nvda", "Random Blog", now),
    ]
    for item in items:
        sw = get_source_weight(item.source, item.url)
        item.source_weight = sw
        base = 10  # Simulated base score from ticker/event matching
        total = base + sw * 5
        print(f"  {item.source:<15} source_weight={sw:.2f}  base_score=10  total={total:.1f}")


if __name__ == "__main__":
    try:
        test_normalize()
        test_source_weight()
        test_dedupe()
        test_freshness()
        test_ranking_integration()
        print("\n=== ALL CHECKS COMPLETED ===")
    except Exception as exc:
        print(f"\nFAIL: {exc}")
        sys.exit(1)
