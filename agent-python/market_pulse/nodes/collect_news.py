from clients.marketaux_client import search_marketaux_news
from clients.fin_news_rss import collect_fin_rss_news
from clients.rss_client import collect_company_market_news
from app.config import settings
from market_pulse.filters.news_filter import dedupe_news
from market_pulse.rankers.news_ranker import parse_news_time
from market_pulse.rankers.source_weight import get_source_weight
from market_pulse.schemas import NewsItem
from market_pulse.state import MarketPulseGraphState


TARGET_CANDIDATE_MIN = 100
TARGET_CANDIDATE_MAX = 300
QUERY_SEARCH_LIMIT = 100
COMPANY_RSS_LIMIT = 180
MARKET_RSS_LIMIT = 240


async def collect_news_node(
    state: MarketPulseGraphState,
) -> MarketPulseGraphState:
    """
    Build a candidate news pool from three sources:
      1. MarketAux keyword search (optional, configurable via COLLECT_ENABLE_MARKETAUX)
      2. Company RSS feeds + Google News fallback (from config/company_feeds.json)
      3. Multi-provider financial RSS (CNBC, MarketWatch, NASDAQ, Seeking Alpha,
         Yahoo Finance, WSJ)

    All sources are fail-soft — if one errors, the others still contribute.
    After collection, dedup and trim to TARGET_CANDIDATE_MAX, sorted by timestamp
    recency then source credibility.
    """
    print("[langgraph-market] collect_news")
    query = state.get("query", "").strip()
    tickers = state.get("tickers", [])
    candidate_news = []
    marketaux_count = 0
    company_rss_count = 0
    market_rss_count = 0

    # RSS is the primary source. Marketaux is an optional supplement
    # (one query) and can be disabled via COLLECT_ENABLE_MARKETAUX to avoid
    # its rate limits.
    if query and settings.collect_enable_marketaux:
        try:
            marketaux_items = await search_marketaux_news(
                query=query,
                limit=QUERY_SEARCH_LIMIT,
                language="en",
                translate_to_zh=False,
            )
            marketaux_count = len(marketaux_items)
            candidate_news.extend(marketaux_items)
        except Exception as exc:
            print(f"[langgraph-market] query news search failed: {exc}")

    # Company RSS + Google News fallback from config/company_feeds.json.
    try:
        company_items = await collect_company_market_news(
            limit=COMPANY_RSS_LIMIT,
            language="en",
            translate_to_zh=False,
        )
        company_rss_count = len(company_items)
        candidate_news.extend(company_items)
        print(f"[langgraph-market] company-rss collected={len(company_items)}")
    except Exception as exc:
        print(f"[langgraph-market] company-rss failed: {exc}")

    # Multi-provider RSS aggregation (CNBC, MarketWatch, NASDAQ, Seeking Alpha, Yahoo, WSJ).
    try:
        rss_items = await collect_fin_rss_news(
            limit=MARKET_RSS_LIMIT,
            tickers=tickers if tickers else None,
        )
        market_rss_count = len(rss_items)
        candidate_news.extend(rss_items)
        print(f"[langgraph-market] multi-rss collected={len(rss_items)} tickers={tickers}")
    except Exception as exc:
        print(f"[langgraph-market] multi-rss failed: {exc}")

    raw_count = len(candidate_news)
    print(f"[langgraph-market] raw candidate_news={raw_count}")

    candidate_news = build_candidate_pool(candidate_news)
    deduped_count = len(candidate_news)
    print(
        "[langgraph-market] candidate pool:",
        {
            "after_dedupe_and_cap": deduped_count,
            "target_min": TARGET_CANDIDATE_MIN,
            "target_max": TARGET_CANDIDATE_MAX,
        },
    )

    return {
        "candidate_news": candidate_news,
        "collect_stats": {
            "marketaux": marketaux_count,
            "company_rss": company_rss_count,
            "market_rss": market_rss_count,
            "raw_candidate_count": raw_count,
            "candidate_pool": deduped_count,
        },
    }


def build_candidate_pool(items: list[NewsItem]) -> list[NewsItem]:
    """Build the pre-rank candidate pool; hard filtering happens in rank_news."""
    deduped = dedupe_news(items)
    if len(deduped) <= TARGET_CANDIDATE_MAX:
        return deduped
    return sorted(deduped, key=_candidate_pool_priority, reverse=True)[
        :TARGET_CANDIDATE_MAX
    ]


def _candidate_pool_priority(item: NewsItem) -> tuple[float, float, int]:
    published = parse_news_time(item.published_at)
    timestamp = published.timestamp() if published else 0.0
    content_len = len((item.content or "").strip())
    has_text = 1 if item.title and (content_len >= 40 or item.url) else 0
    return (
        timestamp,
        get_source_weight(item.source, item.url),
        has_text,
    )
