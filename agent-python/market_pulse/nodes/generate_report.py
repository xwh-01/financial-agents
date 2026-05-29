from market_pulse.analyzers.report_generator import (
    build_financial_recommendations,
    build_market_pulse_report,
    predict_ticker_trends,
)
from datetime import datetime, timezone
from market_pulse.repository import save_market_pulse_report
from market_pulse.state import MarketPulseGraphState


def generate_report_node(
    state: MarketPulseGraphState,
) -> MarketPulseGraphState:
    """Assemble trends, recommendations, and the final report payload."""
    print("[langgraph-market] generate_report")
    analyzed_news = state.get("analyzed_news", [])
    trends = predict_ticker_trends(state.get("completed_results", []))
    recommendations = build_financial_recommendations(trends)
    report = build_market_pulse_report(trends, recommendations, analyzed_news)
    risk_review_notes = state.get("risk_review_notes", [])

    if risk_review_notes:
        report = (
            report
            + "\n\nRisk review:\n"
            + "\n".join(f"- {note}" for note in risk_review_notes)
        )

    result = {
        "status": "completed",
        "query": state.get("query", ""),
        "workflow": "langgraph_market_pulse",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_news": len(state.get("selected_news", [])),
        "candidate_news_count": len(state.get("candidate_news", [])),
        "filtered_news_count": len(state.get("ranked_news", [])),
        "analyzed_news_count": len(state.get("analyzed_news", [])),
        "risk_level": state.get("overall_risk_level", "low"),
        "overall_risk_level": state.get("overall_risk_level", "low"),
        "risk_review_notes": risk_review_notes,
        "analyzed_news": [item.model_dump() for item in analyzed_news],
        "trends": [item.model_dump() for item in trends],
        "recommendations": [item.model_dump() for item in recommendations],
        "report": report,
        "error_message": None,
    }

    result["report_id"] = _save_result_report(result)

    return {"result": result}


def _save_result_report(result: dict) -> int:
    news_count = int(
        result.get("total_news")
        or len(result.get("analyzed_items") or result.get("analyzed_news") or [])
    )
    return save_market_pulse_report(
        query=str(result.get("query") or ""),
        news_count=news_count,
        risk_level=str(result.get("risk_level") or "unknown"),
        summary=_extract_report_summary(result),
        report=result,
    )


def _extract_report_summary(result: dict) -> str:
    summary = str(result.get("summary") or "").strip()
    if summary:
        return summary

    report_text = str(result.get("report") or result.get("final_report") or "").strip()
    if report_text:
        return _compact_summary(report_text)

    query = str(result.get("query") or "").strip()
    if query:
        return f"Market Pulse report for query: {query}"

    return "Market Pulse report"


def _compact_summary(text: str, max_length: int = 180) -> str:
    line = next((item.strip() for item in text.splitlines() if item.strip()), "")
    summary = line or " ".join(text.split())

    if len(summary) <= max_length:
        return summary

    return summary[: max_length - 3].rstrip() + "..."
