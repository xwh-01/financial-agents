"""
Multi-provider RSS news aggregator — inspired by fin-news.

Fetches financial news from CNBC, MarketWatch, NASDAQ, CNN Finance,
Seeking Alpha, and Yahoo Finance via public RSS feeds.
No API keys required.
"""

import asyncio
import random
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote_plus, urlparse

import feedparser
import httpx

from market_pulse.schemas import NewsItem

DEFAULT_TIMEOUT = 15
PER_PROVIDER_CAP = 60
DEFAULT_LIMIT = 200
RETRY_MAX = 3
RETRY_BASE_SLEEP = 0.5

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]


def _random_ua() -> str:
    return random.choice(_USER_AGENTS)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _domain(url: str) -> str:
    return urlparse(url).netloc or "rss"


def _as_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


# ──────────────────────────────────────────────
# Provider RSS URL definitions
# ──────────────────────────────────────────────

CNBC_TOPICS = {
    "top_news": 100003114,
    "world_news": 100727362,
    "us_news": 15837362,
    "asia_news": 19832390,
    "europe_news": 19794221,
    "business": 10001147,
    "investing": 15839069,
    "economy": 20910258,
    "technology": 19854910,
    "earnings": 15839135,
    "finance": 10000664,
    "market_insider": 20409666,
    "commentary": 100370673,
    "politics": 10000113,
    "real_estate": 10000115,
    "energy": 19836768,
}

CNBC_URL = "https://www.cnbc.com/id/{topic_id}/device/rss/rss.html"


def _cnbc_urls() -> list[str]:
    return [CNBC_URL.format(topic_id=tid) for tid in CNBC_TOPICS.values()]


MARKETWATCH_URLS = [
    "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines",
    "https://feeds.content.dowjones.io/public/rss/mw_marketpulse",
    "http://feeds.marketwatch.com/marketwatch/bulletins",
]

NASDAQ_TOPICS = [
    "Stocks",
    "Markets",
    "Earnings",
    "Technology",
    "Artificial Intelligence",
    "Commodities",
    "Investing",
]

NASDAQ_URL = "https://www.nasdaq.com/feed/rssoutbound"


def _nasdaq_urls() -> list[str]:
    return [f"{NASDAQ_URL}?category={quote_plus(topic)}" for topic in NASDAQ_TOPICS]


def _nasdaq_ticker_url(ticker: str) -> str:
    return f"{NASDAQ_URL}?symbol={ticker.lower()}"


CNN_TOPICS = [
    "money_topstories",
    "money_markets",
    "money_technology",
    "money_news_companies",
    "money_news_economy",
]

CNN_URL = "https://rss.cnn.com/rss/{topic}.rss"


def _cnn_urls() -> list[str]:
    return [CNN_URL.format(topic=t) for t in CNN_TOPICS]


SEEKING_ALPHA_URLS = [
    "https://seekingalpha.com/feed.xml",
    "https://seekingalpha.com/market_currents.xml",
]

SEEKING_ALPHA_TICKER_URL = "https://seekingalpha.com/api/sa/combined/{ticker}.xml"


def _sa_urls() -> list[str]:
    return list(SEEKING_ALPHA_URLS)


def _sa_ticker_url(ticker: str) -> str:
    return SEEKING_ALPHA_TICKER_URL.format(ticker=ticker.upper())


YAHOO_URLS = [
    "https://finance.yahoo.com/news/rssindex",
]

YAHOO_HEADLINE_URL = (
    "https://feeds.finance.yahoo.com/rss/2.0/headline"
    "?s={symbols}&region=US&lang=en-US"
)


def _yahoo_urls() -> list[str]:
    return list(YAHOO_URLS)


def _yahoo_ticker_url(tickers: list[str]) -> str:
    return YAHOO_HEADLINE_URL.format(symbols=",".join(tickers[:20]))


WSJ_TOPICS = [
    "WSJcomUSBusiness",
]

WSJ_URL = "https://feeds.a.dj.com/rss/{topic}.xml"


def _wsj_urls() -> list[str]:
    return [WSJ_URL.format(topic=t) for t in WSJ_TOPICS]


# ──────────────────────────────────────────────
# Parsing helpers — convert RSS entries to NewsItem
# ──────────────────────────────────────────────

def _parse_feed(response_bytes: bytes) -> list[dict]:
    """Parse raw RSS/XML bytes into a list of dicts (title/link/content/published)."""
    parsed = feedparser.parse(response_bytes)
    entries: list[dict] = []
    for entry in parsed.entries:
        title = _as_text(entry.get("title"))
        link = _as_text(entry.get("link"))

        # Extract content from whichever field has data.
        raw_content = ""
        if isinstance(entry.get("content"), list) and len(entry["content"]) > 0:
            raw_content = entry["content"][0].get("value", "")
        if not raw_content:
            raw_content = entry.get("summary") or entry.get("description") or ""
        content = _as_text(raw_content)

        published = _as_text(entry.get("published") or entry.get("updated"))
        if not title and not content:
            continue
        entries.append(
            {"title": title, "link": link, "content": content, "published": published}
        )
    return entries


def _to_news_items(
    entries: list[dict],
    source: str,
    provider: str = "rss",
) -> list[NewsItem]:
    """Convert raw RSS dict entries into NewsItem models."""
    items: list[NewsItem] = []
    for idx, e in enumerate(entries):
        items.append(
            NewsItem(
                index=idx,
                title=e["title"],
                content=e["content"],
                source=source,
                url=e["link"],
                published_at=e["published"],
                fetched_at=_utc_now_iso(),
                provider=provider,
            )
        )
    return items


async def _fetch_url(
    client: httpx.AsyncClient,
    url: str,
    source_label: str,
) -> list[NewsItem]:
    """Fetch a single RSS URL with retry and exponential backoff."""
    headers = {
        "User-Agent": _random_ua(),
        "Accept": "application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.7",
    }
    last_exc = None
    for attempt in range(RETRY_MAX):
        try:
            resp = await client.get(url, headers=headers, follow_redirects=True)
            resp.raise_for_status()
            entries = _parse_feed(resp.content)
            items = _to_news_items(entries, source=_domain(url), provider=source_label)
            if attempt > 0:
                print(f"[fin-rss] {source_label:22s} recovered on attempt {attempt+1}")
            print(f"[fin-rss] {source_label:22s} items={len(items):3d} {url[:80]}")
            return items
        except Exception as exc:
            last_exc = exc
            if attempt < RETRY_MAX - 1:
                sleep_s = RETRY_BASE_SLEEP * (2 ** attempt)
                await asyncio.sleep(sleep_s)
    print(f"[fin-rss] {source_label:22s} FAILED  {url[:80]}  -> {last_exc}")
    return []


async def _fetch_urls(
    client: httpx.AsyncClient,
    urls: list[str],
    source_label: str,
) -> list[NewsItem]:
    """Fetch multiple RSS URLs for a single provider."""
    all_items: list[NewsItem] = []
    for url in urls:
        items = await _fetch_url(client, url, source_label)
        all_items.extend(items)
    return all_items


# ──────────────────────────────────────────────
# Main public API
# ──────────────────────────────────────────────

async def collect_fin_rss_news(
    limit: int = DEFAULT_LIMIT,
    tickers: Optional[list[str]] = None,
) -> list[NewsItem]:
    """
    Fetch financial news from multiple providers via RSS.

    Args:
        limit: Maximum number of news items to return.
        tickers: Optional list of ticker symbols for targeted news.

    Returns:
        A deduplicated list of NewsItem objects.
    """
    all_items: list[NewsItem] = []

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        cnbc_items = await _fetch_urls(client, _cnbc_urls(), "cnbc")
        all_items.extend(cnbc_items)

        mw_items = await _fetch_urls(client, MARKETWATCH_URLS, "marketwatch")
        all_items.extend(mw_items)

        nasdaq_items = await _fetch_urls(client, _nasdaq_urls(), "nasdaq")
        all_items.extend(nasdaq_items)

        cnn_items = await _fetch_urls(client, _cnn_urls(), "cnn")
        all_items.extend(cnn_items)

        sa_items = await _fetch_urls(client, _sa_urls(), "seeking_alpha")
        all_items.extend(sa_items)

        yh_items = await _fetch_urls(client, _yahoo_urls(), "yahoo")
        all_items.extend(yh_items)

        wsj_items = await _fetch_urls(client, _wsj_urls(), "wsj")
        all_items.extend(wsj_items)

        # Ticker-targeted feeds (if tickers provided)
        if tickers:
            ticker_set = set(t.upper().strip() for t in tickers if t)
            if ticker_set:
                # NASDAQ ticker feeds
                for t in ticker_set:
                    items = await _fetch_url(
                        client, _nasdaq_ticker_url(t), f"nasdaq-ticker-{t}"
                    )
                    all_items.extend(items)

                # Seeking Alpha ticker feeds
                for t in list(ticker_set)[:5]:
                    items = await _fetch_url(
                        client, _sa_ticker_url(t), f"sa-ticker-{t}"
                    )
                    all_items.extend(items)

                # Yahoo Finance ticker headlines (batch of up to 20)
                yh_ticker_url = _yahoo_ticker_url(list(ticker_set))
                items = await _fetch_url(
                    client, yh_ticker_url, "yahoo-headlines"
                )
                all_items.extend(items)

                print(f"[fin-rss] ticker feeds extra items collected")

    # Cap each provider for diversity, then dedupe.
    capped: list[NewsItem] = []
    from collections import Counter as _Counter
    provider_counts: dict[str, int] = {}
    for item in all_items:
        p = item.provider
        cur = provider_counts.get(p, 0)
        if cur < PER_PROVIDER_CAP:
            capped.append(item)
            provider_counts[p] = cur + 1

    deduped = _dedupe(capped)
    print(
        "[fin-rss] "
        f"raw={len(all_items)} capped={len(capped)} deduped={len(deduped)}"
    )

    return deduped[:max(0, limit)]


def _dedupe(items: list[NewsItem]) -> list[NewsItem]:
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    result: list[NewsItem] = []

    for item in items:
        uk = (item.url or "").strip().lower()
        tk = (item.title or "").strip().lower()

        if uk and uk in seen_urls:
            continue
        if tk and tk in seen_titles:
            continue

        if uk:
            seen_urls.add(uk)
        if tk:
            seen_titles.add(tk)
        result.append(item)

    return result
