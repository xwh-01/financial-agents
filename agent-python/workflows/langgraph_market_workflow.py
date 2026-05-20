import asyncio
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.errors import ExternalServiceError
from schemas.news import NewsItem
from schemas.request import AnalyzeRequest
from schemas.trend import DailyNewsAnalysis
from schemas.workflow import WorkflowResult
from storage.report_store import save_report
from tools.news_collector import collect_latest_market_news
from tools.news_ranker import filter_and_rank_news
from tools.news_search import search_news
from workflows.market_impact_workflow import run_market_impact_workflow
from agents.trend_predictor import (
    build_financial_recommendations,
    build_market_pulse_report,
    predict_ticker_trends,
)


class MarketPulseGraphState(TypedDict, total=False):
    query: str
    max_items: int
    candidate_news: list[NewsItem]
    ranked_news: list[NewsItem]
    selected_news: list[NewsItem]
    analyzed_news: list[DailyNewsAnalysis]
    completed_results: list[WorkflowResult]
    overall_risk_level: str
    risk_review_notes: list[str]
    result: dict[str, Any]
    error_message: str | None


async def _collect_news_node(
    state: MarketPulseGraphState,
) -> MarketPulseGraphState:
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


def _rank_news_node(state: MarketPulseGraphState) -> MarketPulseGraphState:
    print("[langgraph-market] rank_news")
    ranked_news = filter_and_rank_news(state.get("candidate_news", []))
    analysis_limit = max(1, min(state.get("max_items", 5), 5))

    return {
        "ranked_news": ranked_news,
        "selected_news": ranked_news[:analysis_limit],
    }


async def _analyze_items_node(
    state: MarketPulseGraphState,
) -> MarketPulseGraphState:
    print("[langgraph-market] analyze_items")
    analyzed_news: list[DailyNewsAnalysis] = []
    completed_results: list[WorkflowResult] = []

    for item in state.get("selected_news", []):
        try:
            analyze_request = AnalyzeRequest(
                title=item.title,
                content=item.content,
                source=item.source or "news",
                published_at=item.published_at,
            )
            analysis_result = await asyncio.wait_for(
                run_market_impact_workflow(analyze_request),
                timeout=90,
            )

            analyzed_news.append(
                DailyNewsAnalysis(
                    news=item,
                    analysis_result=analysis_result,
                    status=analysis_result.status,
                    error_message=analysis_result.error_message,
                )
            )

            if analysis_result.error_message is None:
                completed_results.append(analysis_result)

        except Exception as exc:
            error_message = (
                "analysis timed out after 90 seconds"
                if isinstance(exc, asyncio.TimeoutError)
                else str(exc)
            )
            analyzed_news.append(
                DailyNewsAnalysis(
                    news=item,
                    analysis_result=None,
                    status="failed",
                    error_message=error_message,
                )
            )

    return {
        "analyzed_news": analyzed_news,
        "completed_results": completed_results,
        "overall_risk_level": _overall_risk_level(completed_results),
    }


def _risk_route_node(
    state: MarketPulseGraphState,
) -> MarketPulseGraphState:
    print("[langgraph-market] risk_route")
    return {}


def _route_after_risk(
    state: MarketPulseGraphState,
) -> Literal["risk_review", "generate_report"]:
    if state.get("overall_risk_level") == "high":
        return "risk_review"
    return "generate_report"


def _risk_review_node(state: MarketPulseGraphState) -> MarketPulseGraphState:
    print("[langgraph-market] risk_review")
    notes: list[str] = []

    for item in state.get("analyzed_news", []):
        result = item.analysis_result
        if not result or not result.risk_result:
            continue

        if result.risk_result.risk_level == "high":
            notes.append(result.risk_result.reason)

        if result.compliance_result and not result.compliance_result.passed:
            notes.extend(result.compliance_result.violations)

    return {"risk_review_notes": _dedupe(notes)}


def _generate_report_node(
    state: MarketPulseGraphState,
) -> MarketPulseGraphState:
    print("[langgraph-market] generate_report")
    trends = predict_ticker_trends(state.get("completed_results", []))
    recommendations = build_financial_recommendations(trends)
    report = build_market_pulse_report(trends, recommendations)
    risk_review_notes = state.get("risk_review_notes", [])

    if risk_review_notes:
        report = report + "\n\nRisk review:\n" + "\n".join(
            f"- {note}" for note in risk_review_notes
        )

    result = {
        "status": "completed",
        "query": state.get("query", ""),
        "workflow": "langgraph_market_pulse",
        "total_news": len(state.get("selected_news", [])),
        "candidate_news_count": len(state.get("candidate_news", [])),
        "filtered_news_count": len(state.get("ranked_news", [])),
        "analyzed_news_count": len(state.get("analyzed_news", [])),
        "risk_level": state.get("overall_risk_level", "low"),
        "overall_risk_level": state.get("overall_risk_level", "low"),
        "risk_review_notes": risk_review_notes,
        "analyzed_news": [
            item.model_dump() for item in state.get("analyzed_news", [])
        ],
        "trends": [item.model_dump() for item in trends],
        "recommendations": [item.model_dump() for item in recommendations],
        "report": report,
        "error_message": None,
    }

    return {"result": result}


def _build_langgraph_market_pulse():
    graph = StateGraph(MarketPulseGraphState)

    graph.add_node("collect_news", _collect_news_node)
    graph.add_node("rank_news", _rank_news_node)
    graph.add_node("analyze_items", _analyze_items_node)
    graph.add_node("risk_route", _risk_route_node)
    graph.add_node("risk_review", _risk_review_node)
    graph.add_node("generate_report", _generate_report_node)

    graph.add_edge(START, "collect_news")
    graph.add_edge("collect_news", "rank_news")
    graph.add_edge("rank_news", "analyze_items")
    graph.add_edge("analyze_items", "risk_route")
    graph.add_conditional_edges(
        "risk_route",
        _route_after_risk,
        {
            "risk_review": "risk_review",
            "generate_report": "generate_report",
        },
    )
    graph.add_edge("risk_review", "generate_report")
    graph.add_edge("generate_report", END)

    return graph.compile()


langgraph_market_pulse = _build_langgraph_market_pulse()


async def run_langgraph_market_pulse(query: str, max_items: int = 5) -> dict:
    try:
        final_state = await langgraph_market_pulse.ainvoke(
            {
                "query": query,
                "max_items": max_items,
                "error_message": None,
            }
        )
        result = final_state["result"]
        report_id = _save_result_report(result)
        result["report_id"] = report_id
        return result

    except ExternalServiceError:
        raise
    except Exception as exc:
        raise ExternalServiceError(
            f"LangGraph market pulse workflow failed: {exc}"
        ) from exc


def _save_result_report(result: dict) -> int:
    try:
        news_count = int(
            result.get("total_news")
            or len(result.get("analyzed_items") or result.get("analyzed_news") or [])
        )
        return save_report(
            query=str(result.get("query") or ""),
            news_count=news_count,
            risk_level=str(result.get("risk_level") or "unknown"),
            summary=str(result.get("summary") or ""),
            report=result,
        )
    except Exception as exc:
        raise ExternalServiceError(
            f"Failed to save LangGraph market pulse report: {exc}"
        ) from exc


def _overall_risk_level(results: list[WorkflowResult]) -> str:
    risk_rank = {"low": 0, "medium": 1, "high": 2}
    level = "low"

    for result in results:
        if not result.risk_result:
            continue
        candidate = result.risk_result.risk_level
        if risk_rank.get(candidate, 0) > risk_rank.get(level, 0):
            level = candidate

    return level


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result: list[str] = []

    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)

    return result
