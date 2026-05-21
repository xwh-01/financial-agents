from market_pulse.rankers.news_ranker import filter_and_rank_news
from market_pulse.state import MarketPulseGraphState


def rank_news_node(state: MarketPulseGraphState) -> MarketPulseGraphState:
    """Score and trim candidate news before expensive per-item analysis."""
    print("[langgraph-market] rank_news")
    ranked_news = filter_and_rank_news(state.get("candidate_news", []))
    analysis_limit = max(1, min(state.get("max_items", 5), 5))

    return {
        "ranked_news": ranked_news,
        "selected_news": ranked_news[:analysis_limit],
    }
