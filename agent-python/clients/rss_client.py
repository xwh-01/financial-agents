import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict
from urllib.parse import quote_plus
from urllib.parse import urlparse

try:
    import feedparser
except ModuleNotFoundError:
    feedparser = None

from clients.retry import get_bytes_with_retry
from clients.marketaux_client import collect_latest_marketaux_news
from app.config import settings
from market_pulse.schemas import NewsItem

logger = logging.getLogger(__name__)


GOOGLE_NEWS_RSS_TEMPLATE = (
    "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
)

RSS_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.7",
}


class CompanyFeedConfig(TypedDict):
    company: str
    ticker: str
    rss_feeds: list[str]
    search_queries: list[str]


class MarketFeedConfig(TypedDict):
    name: str
    rss_feeds: list[str]


def load_company_feeds() -> list[CompanyFeedConfig]:
    path = _config_path()

    if not path.exists():
        logger.warning("company-feeds config not found: %s", path)
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            logger.warning("company-feeds invalid config root, expected list: %s", path)
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

        print(f"[company-feeds] loaded companies={len(configs)} path={path}")
        return configs

    except Exception as exc:
        logger.warning("company-feeds failed to load %s: %s", path, exc)
        return []


def load_market_feeds() -> list[MarketFeedConfig]:
    path = _market_config_path()

    if not path.exists():
        logger.warning("market-feeds config not found: %s", path)
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            logger.warning("market-feeds invalid config root, expected list: %s", path)
            return []

        configs: list[MarketFeedConfig] = []
        for item in raw:
            if not isinstance(item, dict):
                continue

            name = _as_text(item.get("name"))
            rss_feeds = _as_str_list(item.get("rss_feeds"))
            if not name or not rss_feeds:
                continue

            configs.append({"name": name, "rss_feeds": rss_feeds})

        print(f"[market-feeds] loaded groups={len(configs)} path={path}")
        return configs

    except Exception as exc:
        logger.warning("market-feeds failed to load %s: %s", path, exc)
        return []


async def fetch_rss_feed(url: str, limit: int = 20) -> list[NewsItem]:
    if feedparser is None:
        print("[rss] feedparser is not installed; skip RSS feed")
        return []

    content = await get_bytes_with_retry(
        url,
        headers=RSS_REQUEST_HEADERS,
        timeout=settings.rss_timeout_seconds,
        max_retries=settings.llm_retry_attempts,
        backoff_seconds=settings.llm_retry_backoff_seconds,
        error_type="rss_fetch_failed",
    )

    parsed = feedparser.parse(content)
    feed_title = parsed.feed.get("title") if parsed.feed else ""
    source = feed_title or _domain_from_url(url)
    items: list[NewsItem] = []

    for idx, entry in enumerate(parsed.entries[: max(0, limit)]):
        title = _as_text(entry.get("title"))
        content = _as_text(
            entry.get("summary") or entry.get("description") or entry.get("subtitle")
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
                fetched_at=_utc_now_iso(),
                provider="rss",
            )
        )

    return items


async def fetch_rss_feeds(
    urls: list[str],
    limit_per_feed: int = 20,
    source_label: str = "rss",
) -> list[NewsItem]:
    items: list[NewsItem] = []

    for url in urls:
        try:
            feed_items = await fetch_rss_feed(url, limit=limit_per_feed)
            print(f"[rss] source={source_label} url={url} items={len(feed_items)}")
            items.extend(feed_items)
        except Exception as exc:
            print(f"[rss] source={source_label} url={url} failed: {exc}")

    return items


async def collect_company_market_news(
    limit: int,
    language: str,
    translate_to_zh: bool,
) -> list[NewsItem]:
    all_items: list[NewsItem] = []

    if settings.collect_enable_marketaux:
        try:
            all_items.extend(
                await collect_latest_marketaux_news(
                    limit=limit,
                    language=language,
                    translate_to_zh=translate_to_zh,
                )
            )
        except Exception as exc:
            print(f"[source-aggregator] Marketaux failed: {exc}")

    configs = load_company_feeds()
    market_configs = load_market_feeds()

    if settings.enable_company_rss and configs:
        rss_urls = _company_rss_urls(configs)
        fallback_urls = _google_news_fallback_urls(configs)
        for config in configs:
            print(
                "[company-feeds] "
                f"company={config['company']} ticker={config['ticker']} "
                f"rss_feeds={len(config['rss_feeds'])} "
                f"search_queries={len(config['search_queries'])}"
            )

        try:
            rss_items = await fetch_rss_feeds(
                rss_urls,
                limit_per_feed=settings.min_news_count,
                source_label="company-rss",
            )
            print(f"[source-aggregator] company rss total={len(rss_items)}")
            all_items.extend(rss_items)
        except Exception as exc:
            print(f"[source-aggregator] company rss failed: {exc}")
            rss_items = []

        if len(rss_items) < settings.min_news_count:
            try:
                fallback_items = await fetch_rss_feeds(
                    fallback_urls,
                    limit_per_feed=max(1, min(settings.min_news_count, 20)),
                    source_label="google-news-fallback",
                )
                print(
                    "[source-aggregator] "
                    f"google news rss fallback total={len(fallback_items)}"
                )
                all_items.extend(fallback_items)
            except Exception as exc:
                print(f"[source-aggregator] google news rss fallback failed: {exc}")
        else:
            print(
                "[source-aggregator] "
                f"skip fallback, company rss items={len(rss_items)} "
                f"threshold={settings.min_news_count}"
            )

    if settings.enable_market_rss and market_configs:
        market_urls = _market_rss_urls(market_configs)
        for config in market_configs:
            print(
                "[market-feeds] "
                f"name={config['name']} rss_feeds={len(config['rss_feeds'])}"
            )

        try:
            market_items = await fetch_rss_feeds(
                market_urls,
                limit_per_feed=max(3, min(settings.min_news_count, 10)),
                source_label="market-rss",
            )
            print(f"[source-aggregator] market rss total={len(market_items)}")
            all_items.extend(market_items)
        except Exception as exc:
            print(f"[source-aggregator] market rss failed: {exc}")

    deduped = dedupe_news_items(all_items)
    print(
        f"[source-aggregator] total before dedupe={len(all_items)} "
        f"after dedupe={len(deduped)}"
    )
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


def _market_rss_urls(configs: list[MarketFeedConfig]) -> list[str]:
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
        if _contains_company_name(text, company) or _contains_ticker(text, ticker):
            if config["ticker"] not in matched:
                matched.append(config["ticker"])

    item.matched_tickers = matched


def _contains_ticker(text: str, ticker: str) -> bool:
    return re.search(rf"\b{re.escape(ticker)}\b", text, re.IGNORECASE) is not None


def _contains_company_name(text: str, company: str) -> bool:
    """Check if a company name appears as a whole word/phrase in the text."""
    if not company:
        return False
    return re.search(rf"\b{re.escape(company)}\b", text, re.IGNORECASE) is not None


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


def _market_config_path() -> Path:
    configured = Path(settings.market_feeds_path)
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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
