import re
from urllib.parse import quote_plus

from app.config import settings
from market_pulse.schemas import NewsItem
from clients.news_client import collect_latest_market_news
from tools.company_feed_config import CompanyFeedConfig, load_company_feeds
from tools.rss_collector import fetch_rss_feeds


GOOGLE_NEWS_RSS_TEMPLATE = (
    "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
)


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
