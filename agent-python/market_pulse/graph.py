from langgraph.graph import END, START, StateGraph

from app.errors import ExternalServiceError
from market_pulse.api_metrics import reset_api_metrics
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
from market_pulse.trace import new_trace_id, save_trace, trace_node


def _build_langgraph_market_pulse():
    """
    Build the Market Pulse LangGraph workflow.

    Pipeline: collect_news -> rank_news -> analyze_items -> risk_route
              -> [risk_review if high-risk else skip] -> generate_report

    All nodes are wrapped with trace_node for per-step observability (timing,
    events, error recording). The compiled graph is stored as a module-level
    singleton for reuse across requests.
    """
    graph = StateGraph(MarketPulseGraphState)

    graph.add_node("collect_news", trace_node("collect_news", collect_news_node))
    graph.add_node("rank_news", trace_node("rank_news", rank_news_node))
    graph.add_node("analyze_items", trace_node("analyze_items", analyze_items_node))
    graph.add_node("risk_route", trace_node("risk_route", risk_route_node))
    graph.add_node("risk_review", trace_node("risk_review", risk_review_node))
    graph.add_node("generate_report", trace_node("generate_report", generate_report_node))

    # Linear chain: START -> collect -> rank -> analyze -> risk_route
    graph.add_edge(START, "collect_news")
    graph.add_edge("collect_news", "rank_news")
    graph.add_edge("rank_news", "analyze_items")
    graph.add_edge("analyze_items", "risk_route")

    # Conditional branch after risk assessment:
    #   - If overall_risk_level == "high", go through risk_review for human-visible notes
    #   - Otherwise skip directly to report generation
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


async def run_langgraph_market_pulse(
    query: str,
    max_items: int = 8,
    tickers: list[str] | None = None,
    report_job_id: int | None = None,
    report_trace_id: int | None = None,
) -> dict:
    """
    Execute the full Market Pulse pipeline via LangGraph.

    This is the recommended demo entry point (POST /api/agent/market-pulse/langgraph).
    Initializes a fresh trace and API metrics counter, runs the graph, then saves
    the trace to disk and attaches trace metadata to the result dict.

    Raises ExternalServiceError on any failure so the caller gets a clean error shape.
    """
    try:
        trace_id = new_trace_id()
        # Reset per-run API call counters before starting the pipeline
        reset_api_metrics()
        initial_state: MarketPulseGraphState = {
            "trace_id": trace_id,
            "trace_events": [],
            "query": query,
            "max_items": max_items,
            "tickers": tickers or [],
            "error_message": None,
        }
        if report_job_id is not None and report_trace_id is not None:
            initial_state["report_job_id"] = report_job_id
            initial_state["report_trace_id"] = report_trace_id
        final_state = await langgraph_market_pulse.ainvoke(initial_state)
        if "result" not in final_state:
            raise ExternalServiceError(
                "Market Pulse pipeline did not produce a result. "
                "Check earlier node failures (collect_news, rank_news, analyze_items). "
                f"error_message={final_state.get('error_message')}"
            )
        result = dict(final_state["result"])
        trace_events = list(final_state.get("trace_events") or [])
        trace_path = save_trace(trace_id, trace_events)
        result["trace_id"] = trace_id
        result["trace_events"] = trace_events
        result["trace_path"] = trace_path
        return result

    except ExternalServiceError:
        raise
    except Exception as exc:
        raise ExternalServiceError(
            f"LangGraph market pulse workflow failed: {exc}"
        ) from exc
