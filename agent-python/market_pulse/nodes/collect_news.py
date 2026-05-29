from clients.news_client import search_news
from clients.fin_news_rss import collect_fin_rss_news
from clients.rss_client import collect_company_market_news
from market_pulse.filters.news_filter import dedupe_news, filter_fresh_news
from market_pulse.state import MarketPulseGraphState


async def collect_news_node(
    state: MarketPulseGraphState,
) -> MarketPulseGraphState:
    """Build candidate news pool from query search + multi-provider RSS + ticker feeds."""
    print("[langgraph-market] collect_news")
    query = state.get("query", "").strip()
    tickers = state.get("tickers", [])
    candidate_news = []

    # Try query-based news API search first (if configured).
    if query:
        try:
            candidate_news.extend(
                await search_news(
                    query=query,
                    limit=50,
                    language="en",
                    translate_to_zh=False,
                )
            )
        except Exception as exc:
            print(f"[langgraph-market] query news search failed: {exc}")

    # Company RSS + Google News fallback from config/company_feeds.json.
    try:
        company_items = await collect_company_market_news(
            limit=150,
            language="en",
            translate_to_zh=False,
        )
        candidate_news.extend(company_items)
        print(f"[langgraph-market] company-rss collected={len(company_items)}")
    except Exception as exc:
        print(f"[langgraph-market] company-rss failed: {exc}")

    # Multi-provider RSS aggregation (CNBC, MarketWatch, NASDAQ, Seeking Alpha, Yahoo, WSJ).
    try:
        rss_items = await collect_fin_rss_news(limit=200, tickers=tickers if tickers else None)
        candidate_news.extend(rss_items)
        print(f"[langgraph-market] multi-rss collected={len(rss_items)} tickers={tickers}")
    except Exception as exc:
        print(f"[langgraph-market] multi-rss failed: {exc}")

    raw_count = len(candidate_news)
    print(f"[langgraph-market] raw candidate_news={raw_count}")

    candidate_news = dedupe_news(candidate_news)
    deduped_count = len(candidate_news)
    print(f"[langgraph-market] after dedupe={deduped_count}")

    candidate_news = filter_fresh_news(candidate_news, max_age_hours=72)
    fresh_count = len(candidate_news)
    print(f"[langgraph-market] after freshness filter={fresh_count}")

    return {"candidate_news": candidate_news}
