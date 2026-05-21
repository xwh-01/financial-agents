"""Repository facade for Market Pulse report persistence."""

from storage.report_store import get_report as _get_report
from storage.report_store import list_reports as _list_reports
from storage.report_store import save_report as _save_report


def save_market_pulse_report(
    query: str,
    news_count: int,
    risk_level: str,
    summary: str,
    report: dict,
) -> int:
    return _save_report(
        query=query,
        news_count=news_count,
        risk_level=risk_level,
        summary=summary,
        report=report,
    )


def list_reports(limit: int = 20) -> list[dict]:
    return _list_reports(limit=limit)


def get_report(report_id: int) -> dict | None:
    return _get_report(report_id)
