from pydantic import BaseModel


class ReportResponse(BaseModel):
    id: int
    user_id: int | None = None
    watchlist_id: int | None = None
    title: str | None = None
    query: str
    summary: str | None = None
    risk_level: str | None = None
    report_type: str | None = None
    created_at: str | None = None


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
