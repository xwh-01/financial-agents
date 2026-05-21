from clients.news_client import collect_latest_market_news, search_news
from market_pulse.state import MarketPulseGraphState


async def collect_news_node(
    state: MarketPulseGraphState,
) -> MarketPulseGraphState:
    """Build the candidate news pool from query search or latest market news."""
    print("[langgraph-market] collect_news")
    query = state.get("query", "").strip()

    if query:
        candidate_news = await search_news(
            query=query,
            limit=50,
            language="en",
            translate_to_zh=False,
        )
    else:
        candidate_news = await collect_latest_market_news(
            limit=50,
            language="en",
            translate_to_zh=False,
        )

    return {"candidate_news": candidate_news}
