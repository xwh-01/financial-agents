from typing import Any, TypedDict

from market_pulse.schemas import DailyNewsAnalysis, NewsItem, WorkflowResult


class MarketPulseGraphState(TypedDict, total=False):
    query: str
    max_items: int
    tickers: list[str]
    candidate_news: list[NewsItem]
    ranked_news: list[NewsItem]
    selected_news: list[NewsItem]
    analyzed_news: list[DailyNewsAnalysis]
    completed_results: list[WorkflowResult]
    overall_risk_level: str
    risk_review_notes: list[str]
    trace_id: str
    trace_events: list[dict[str, Any]]
    result: dict[str, Any]
    error_message: str | None
