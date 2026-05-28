from langgraph.graph import END, START, StateGraph

from app.errors import ExternalServiceError
from market_pulse.nodes.analyze_items import analyze_items_node
from market_pulse.nodes.collect_news import collect_news_node
from market_pulse.nodes.generate_report import generate_report_node
from market_pulse.nodes.rank_news import rank_news_node
from market_pulse.nodes.risk_review import (
    risk_review_node,
    risk_route_node,
    route_after_risk,
)
from market_pulse.state import MarketPulseGraphState


def _build_langgraph_market_pulse():
    graph = StateGraph(MarketPulseGraphState)

    graph.add_node("collect_news", collect_news_node)
    graph.add_node("rank_news", rank_news_node)
    graph.add_node("analyze_items", analyze_items_node)
    graph.add_node("risk_route", risk_route_node)
    graph.add_node("risk_review", risk_review_node)
    graph.add_node("generate_report", generate_report_node)

    graph.add_edge(START, "collect_news")
    graph.add_edge("collect_news", "rank_news")
    graph.add_edge("rank_news", "analyze_items")
    graph.add_edge("analyze_items", "risk_route")
    graph.add_conditional_edges(
        "risk_route",
        route_after_risk,
        {
            "risk_review": "risk_review",
            "generate_report": "generate_report",
        },
    )
    graph.add_edge("risk_review", "generate_report")
    graph.add_edge("generate_report", END)

    return graph.compile()


langgraph_market_pulse = _build_langgraph_market_pulse()


async def run_langgraph_market_pulse(query: str, max_items: int = 5, tickers: list[str] | None = None) -> dict:
    try:
        final_state = await langgraph_market_pulse.ainvoke(
            {
                "query": query,
                "max_items": max_items,
                "tickers": tickers or [],
                "error_message": None,
            }
        )
        return final_state["result"]

    except ExternalServiceError:
        raise
    except Exception as exc:
        raise ExternalServiceError(
            f"LangGraph market pulse workflow failed: {exc}"
        ) from exc
