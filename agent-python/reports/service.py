from typing import Any

from reports import repository
from reports.schemas import ReportDetailResponse, ReportItemResponse, ReportResponse


def save_watchlist_report(
    user_id: int,
    watchlist_id: int,
    title: str,
    query: str,
    result: dict,
) -> int:
    report_id = repository.save_report(
        user_id=user_id,
        watchlist_id=watchlist_id,
        title=title,
        query=query,
        summary=_extract_summary(result),
        risk_level=_extract_risk_level(result),
        report_type="watchlist",
        report_json=result,
    )
    repository.save_report_items(
        report_id=report_id,
        items=extract_report_items(result),
    )
    return report_id


def list_user_reports(
    user_id: int,
    watchlist_id: int | None = None,
) -> list[ReportResponse]:
    return [
        ReportResponse(**item)
        for item in repository.list_reports(
            user_id=user_id,
            watchlist_id=watchlist_id,
        )
    ]


def get_user_report_detail(user_id: int, report_id: int) -> ReportDetailResponse | None:
    report = repository.get_report_by_id(user_id=user_id, report_id=report_id)
    if report is None:
        return None

    items = repository.list_report_items(report_id=report_id)
    report.pop("report_json", None)
    return ReportDetailResponse(
        report=ReportResponse(**report),
        items=[ReportItemResponse(**item) for item in items],
    )


def list_user_report_items(user_id: int, report_id: int) -> list[ReportItemResponse] | None:
    report = repository.get_report_by_id(user_id=user_id, report_id=report_id)
    if report is None:
        return None

    return [
        ReportItemResponse(**item)
        for item in repository.list_report_items(report_id=report_id)
    ]


def extract_report_items(result: dict) -> list[dict[str, Any]]:
    raw_items = result.get("analyzed_news") or result.get("analyzed_items") or []
    items = []
    for raw in raw_items:
        try:
            news = raw.get("news") or {}
            analysis = raw.get("analysis_result") or {}
            entity = analysis.get("entity_result") or {}
            event = analysis.get("event_result") or {}
            risk = analysis.get("risk_result") or {}

            tickers = (
                news.get("matched_tickers")
                or entity.get("tickers")
                or (analysis.get("ticker_links") or {}).get("direct_tickers")
                or []
            )
            topics = news.get("matched_topics") or entity.get("topics") or []

            items.append(
                {
                    "title": news.get("title") or "Untitled news",
                    "summary": event.get("summary") or analysis.get("report") or raw.get("error_message"),
                    "impact_analysis": analysis.get("report") or event.get("summary"),
                    "risk_level": risk.get("risk_level"),
                    "tickers": tickers,
                    "topics": topics,
                    "source_name": news.get("source") or news.get("provider"),
                    "source_url": news.get("url"),
                    "published_at": news.get("published_at"),
                    "relevance_score": news.get("relevance_score"),
                }
            )
        except Exception:
            continue
    return items


def _extract_summary(result: dict) -> str:
    summary = str(result.get("summary") or "").strip()
    if summary:
        return summary

    report_text = str(result.get("report") or result.get("final_report") or "").strip()
    if report_text:
        first_line = next((line.strip() for line in report_text.splitlines() if line.strip()), "")
        summary = first_line or " ".join(report_text.split())
        return summary[:177].rstrip() + "..." if len(summary) > 180 else summary

    query = str(result.get("query") or "").strip()
    return f"Market Pulse report for query: {query}" if query else "Market Pulse report"


def _extract_risk_level(result: dict) -> str:
    return str(
        result.get("risk_level")
        or result.get("overall_risk_level")
        or "unknown"
    )
