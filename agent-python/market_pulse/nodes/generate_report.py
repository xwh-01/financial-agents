from market_pulse.analyzers.report_generator import (
    build_market_signal_report,
    build_market_signals,
    build_financial_recommendations,
    predict_ticker_trends,
    synthesize_report,
)
from datetime import datetime, timezone
from market_pulse.api_metrics import get_api_metrics
from market_pulse.repository import save_market_pulse_report
from market_pulse.state import MarketPulseGraphState
from safety.compliance import apply_output_compliance_guard


async def generate_report_node(
    state: MarketPulseGraphState,
) -> MarketPulseGraphState:
    """
    Assemble the final report payload from all preceding pipeline data.

    Build order:
      1. Ticker trends from completed analysis results
      2. Market signals (aggregated from trends + per-item analysis)
      3. Signal report text (Chinese-language narrative)
      4. Legacy recommendations (compatibility only, prefer market_signals)
      5. Synthesis — LLM-generated summary of all single-news reports (only when >= 3 items)
      6. Append risk review notes and market data error messages

    After assembly, the report is run through the output compliance guard
    (forbidden-phrase sanitization + disclaimer injection) and persisted
    via save_market_pulse_report. API call metrics are saved for scheduled
    report job traces.
    """
    print("[langgraph-market] generate_report")
    analyzed_news = state.get("analyzed_news", [])
    trends = predict_ticker_trends(state.get("completed_results", []))
    market_signals = build_market_signals(trends, analyzed_news)
    signal_report = build_market_signal_report(market_signals)
    # Legacy compatibility only. New frontend/report surfaces should use market_signals.
    recommendations = build_financial_recommendations(trends)
    risk_review_notes = state.get("risk_review_notes", [])

    single_reports = [
        item.analysis_result.report
        for item in analyzed_news
        if item.analysis_result and item.analysis_result.report
    ]
    synthesis = ""
    if len(single_reports) >= 3:
        try:
            synthesis = await synthesize_report(single_reports, trends)
            print("[langgraph-market] synthesis generated")
        except Exception as exc:
            print(f"[langgraph-market] synthesis failed: {exc}")

    if synthesis:
        report = synthesis + "\n\n---\n\n" + signal_report
    else:
        report = signal_report

    if risk_review_notes:
        report = (
            report
            + "\n\nRisk review:\n"
            + "\n".join(f"- {note}" for note in risk_review_notes)
        )

    market_error = state.get("error_message", "") or ""
    if market_error:
        report = report + f"\n\nNote: {market_error}"

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
        "market_signals": [item.model_dump() for item in market_signals],
        "recommendations": [item.model_dump() for item in recommendations],
        "report": report,
        "error_message": None,
    }
    result["api_calls"] = get_api_metrics()
    result = apply_output_compliance_guard(result)

    _save_api_call_stats(state, result.get("api_calls") or {})

    result["report_id"] = _save_result_report(result)

    return {"result": result}


def _save_api_call_stats(state: MarketPulseGraphState, api_calls: dict) -> None:
    report_trace_id = state.get("report_trace_id")
    report_job_id = state.get("report_job_id")
    if not report_trace_id or not api_calls:
        return
    try:
        from report_jobs import trace_repository

        trace_repository.save_api_call_stats(
            trace_id=int(report_trace_id),
            job_id=int(report_job_id) if report_job_id is not None else None,
            report_id=None,
            metrics=api_calls,
        )
    except (TypeError, ValueError) as exc:
        print(f"[langgraph-market] save_api_call_stats invalid ids: {exc}")
    except Exception as exc:
        print(f"[langgraph-market] save_api_call_stats failed: {exc}")


def _save_result_report(result: dict) -> int:
    total_news = result.get("total_news")
    if total_news is None:
        total_news = len(result.get("analyzed_news") or [])
    news_count = int(total_news)
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
