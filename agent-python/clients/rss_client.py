import json
import re
from pathlib import Path
from typing import TypedDict
from urllib.parse import quote_plus
from urllib.parse import urlparse

import feedparser
import httpx

from clients.news_client import collect_latest_market_news
from app.config import settings
from market_pulse.schemas import NewsItem


GOOGLE_NEWS_RSS_TEMPLATE = (
    "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
)


class CompanyFeedConfig(TypedDict):
    company: str
    ticker: str
    rss_feeds: list[str]
    search_queries: list[str]


def load_company_feeds() -> list[CompanyFeedConfig]:
    path = _config_path()

    if not path.exists():
        print(f"[company-feeds] config not found: {path}")
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            print(f"[company-feeds] invalid config root, expected list: {path}")
            return []

        configs: list[CompanyFeedConfig] = []
        for item in raw:
            if not isinstance(item, dict):
                continue

            company = _as_text(item.get("company"))
            ticker = _as_text(item.get("ticker")).upper()
            if not company or not ticker:
                continue

            configs.append(
                {
                    "company": company,
                    "ticker": ticker,
                    "rss_feeds": _as_str_list(item.get("rss_feeds")),
                    "search_queries": _as_str_list(item.get("search_queries")),
                }
            )

        return configs

    except Exception as exc:
        print(f"[company-feeds] failed to load {path}: {exc}")
        return []


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


async def collect_company_market_news(
    limit: int,
    language: str,
    translate_to_zh: bool,
) -> list[NewsItem]:
    all_items: list[NewsItem] = []

    try:
        all_items.extend(
            await collect_latest_market_news(
                limit=limit,
                language=language,
                translate_to_zh=translate_to_zh,
            )
        )
    except Exception as exc:
        print(f"[source-aggregator] news api failed: {exc}")

    configs = load_company_feeds()
    if settings.enable_company_rss and configs:
        rss_urls = _company_rss_urls(configs)
        fallback_urls = _google_news_fallback_urls(configs)

        try:
            all_items.extend(
                await fetch_rss_feeds(rss_urls, limit_per_feed=settings.min_news_count)
            )
        except Exception as exc:
            print(f"[source-aggregator] company rss failed: {exc}")

        try:
            all_items.extend(
                await fetch_rss_feeds(
                    fallback_urls,
                    limit_per_feed=max(1, min(settings.min_news_count, 20)),
                )
            )
        except Exception as exc:
            print(f"[source-aggregator] google news rss fallback failed: {exc}")

    deduped = dedupe_news_items(all_items)
    for item in deduped:
        _add_company_tickers(item, configs)

    return deduped[: max(0, limit)]


def build_google_news_rss_url(query: str) -> str:
    return GOOGLE_NEWS_RSS_TEMPLATE.format(query=quote_plus(query.strip()))


def dedupe_news_items(items: list[NewsItem]) -> list[NewsItem]:
    seen_urls = set()
    seen_titles = set()
    result: list[NewsItem] = []

    for item in items:
        url_key = (item.url or "").strip().lower()
        title_key = (item.title or "").strip().lower()

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


def _company_rss_urls(configs: list[CompanyFeedConfig]) -> list[str]:
    urls: list[str] = []
    for config in configs:
        urls.extend(config["rss_feeds"])
    return _dedupe_strings(urls)


def _google_news_fallback_urls(configs: list[CompanyFeedConfig]) -> list[str]:
    urls: list[str] = []
    for config in configs:
        for query in config["search_queries"]:
            urls.append(build_google_news_rss_url(query))
    return _dedupe_strings(urls)


def _add_company_tickers(
    item: NewsItem,
    configs: list[CompanyFeedConfig],
) -> None:
    text = f"{item.title} {item.content}".lower()
    matched = list(item.matched_tickers)

    for config in configs:
        company = config["company"].lower()
        ticker = config["ticker"].lower()
        if company in text or _contains_ticker(text, ticker):
            if config["ticker"] not in matched:
                matched.append(config["ticker"])

    item.matched_tickers = matched


def _contains_ticker(text: str, ticker: str) -> bool:
    return re.search(rf"\b{re.escape(ticker)}\b", text, re.IGNORECASE) is not None


def _dedupe_strings(items: list[str]) -> list[str]:
    seen = set()
    result: list[str] = []

    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)

    return result


def _config_path() -> Path:
    configured = Path(settings.company_feeds_path)
    if configured.is_absolute():
        return configured

    return Path(__file__).resolve().parents[1] / configured


def _domain_from_url(url: str) -> str:
    return urlparse(url).netloc or "rss"


def _as_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_str_list(value) -> list[str]:
    if not isinstance(value, list):
        return []

    result: list[str] = []
    for item in value:
        text = _as_text(item)
        if text:
            result.append(text)

    return result
