from market_pulse.rankers.news_ranker import (
    filter_and_rank_news,
    select_representative_news,
)
from market_pulse.state import MarketPulseGraphState


def rank_news_node(state: MarketPulseGraphState) -> MarketPulseGraphState:
    """Score and trim candidate news before expensive per-item analysis."""
    print("[langgraph-market] rank_news")
    ranked_news = filter_and_rank_news(
        state.get("candidate_news", []),
        query=state.get("query", ""),
    )
    analysis_limit = max(1, min(state.get("max_items", 8), 10))
    selected_news = select_representative_news(
        ranked_news,
        limit=analysis_limit,
        requested_tickers=state.get("tickers", []),
        per_ticker=2,
    )

    return {
        "ranked_news": ranked_news,
        "selected_news": selected_news,
    }
