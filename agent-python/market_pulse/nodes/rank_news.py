from app.config import settings
from market_pulse.rankers.embedding_ranker import embedding_rerank
from market_pulse.rankers.llm_reranker import llm_rerank
from market_pulse.rankers.query_driven_ranker import coarse_filter
from market_pulse.state import MarketPulseGraphState


async def rank_news_node(state: MarketPulseGraphState) -> MarketPulseGraphState:
    """
    3-layer ranking pipeline to narrow candidates down to the final analysis set.

    Layer 1 — Coarse (query_driven_ranker): fast regex matching against query terms,
      drops ~300 candidates to ~60. Guarantees per-intent-token recall so
      multi-ticker watchlists don't collapse to a single theme.

    Layer 2 — Embedding (embedding_ranker): cosine similarity between query embedding
      and article title embeddings, keeps top ~40.

    Layer 3 — LLM (llm_reranker): instructs an LLM to pick the most relevant ~8 articles
      for the query, ensuring coverage of all mentioned tickers/topics.

    Each layer's limit is widened so enough candidates survive to the next stage.
    """
    print("[langgraph-market] rank_news (3-layer pipeline)")
    query = state.get("query", "")
    candidate_news = list(state.get("candidate_news", []))
    max_analyze = max(1, settings.market_pulse_max_analyze)
    requested = state.get("max_items") or max_analyze
    max_items = max(1, min(requested, max_analyze))

    # Widen each layer so up to `max_items` can survive to the LLM analysis step.
    coarse_limit = max(max_items * 2, 60)
    embedding_limit = max(max_items + 20, 40)

    layer1 = coarse_filter(candidate_news, query=query, limit=coarse_limit)
    print(f"[langgraph-market] layer1 (coarse): {len(layer1)} items")

    layer2 = await embedding_rerank(layer1, query=query, limit=embedding_limit)
    print(f"[langgraph-market] layer2 (embedding): {len(layer2)} items")

    selected_news = await llm_rerank(layer2, query=query, limit=max_items)
    print(f"[langgraph-market] layer3 (llm rerank): {len(selected_news)} items")

    return {
        "ranked_news": layer1,
        "selected_news": selected_news,
    }
