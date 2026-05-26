from clients.news_client import search_news
from clients.rss_client import collect_company_market_news, dedupe_news_items
from market_pulse.filters.news_filter import dedupe_news, filter_fresh_news
from market_pulse.state import MarketPulseGraphState


async def collect_news_node(
    state: MarketPulseGraphState,
) -> MarketPulseGraphState:
    """Build the candidate news pool from query search or latest market news."""
    print("[langgraph-market] collect_news")
    query = state.get("query", "").strip()
    candidate_news = []

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

    try:
        candidate_news.extend(
            await collect_company_market_news(
                limit=50,
                language="en",
                translate_to_zh=False,
            )
        )
    except Exception as exc:
        print(f"[langgraph-market] company market news failed: {exc}")

    candidate_news = dedupe_news_items(candidate_news)
    raw_count = len(candidate_news)
    print(f"[langgraph-market] raw candidate_news={raw_count}")

    candidate_news = dedupe_news(candidate_news)
    deduped_count = len(candidate_news)
    print(f"[langgraph-market] after dedupe={deduped_count}")

    candidate_news = filter_fresh_news(candidate_news, max_age_hours=72)
    fresh_count = len(candidate_news)
    print(f"[langgraph-market] after freshness filter={fresh_count}")

    return {"candidate_news": candidate_news}
