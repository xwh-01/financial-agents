from pydantic import BaseModel


class ReportResponse(BaseModel):
    id: int
    user_id: int | None = None
    watchlist_id: int | None = None
    title: str | None = None
    query: str
    summary: str | None = None
    risk_level: str | None = None
    overall_risk_level: str | None = None
    candidate_news_count: int | None = None
    filtered_news_count: int | None = None
    analyzed_news_count: int | None = None
    report_type: str | None = None
    compliance_status: str | None = None
    created_at: str | None = None
    report: str | None = None
    generated_at: str | None = None


class ReportItemResponse(BaseModel):
    id: int
    report_id: int
    title: str
    summary: str | None = None
    impact_analysis: str | None = None
    risk_level: str | None = None
    tickers: str | None = None
    topics: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    published_at: str | None = None
    relevance_score: float | None = None


class ReportDetailResponse(BaseModel):
    report: ReportResponse
    items: list[ReportItemResponse]
    disclaimer: str | None = None
