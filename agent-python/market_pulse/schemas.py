from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    title: str
    content: str
    source: str
    published_at: str


class ComplianceResult(BaseModel):
    passed: bool
    violations: list[str] = Field(default_factory=list)
    required_disclaimer_present: bool
    sanitized_report: str


class EntityResult(BaseModel):
    persons: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    tickers: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class EventResult(BaseModel):
    event_type: str
    summary: str
    sentiment: str
    impact_score: float
    confidence: float


class MarketMetric(BaseModel):
    return_1d: float | None = None
    return_3d: float | None = None
    return_7d: float | None = None
    volume_change: float | None = None
    relative_to_spy_3d: float | None = None


class MarketMetrics(BaseModel):
    metrics: dict[str, MarketMetric] = Field(default_factory=dict)


class ReportResult(BaseModel):
    content: str
    sections: list[str] = Field(default_factory=list)


class RiskResult(BaseModel):
    risk_level: str
    risk_flags: list[str] = Field(default_factory=list)
    reason: str


class TickerLinks(BaseModel):
    direct_tickers: list[str] = Field(default_factory=list)
    related_tickers: list[str] = Field(default_factory=list)
    etfs: list[str] = Field(default_factory=list)
    reason: str = ""
    confidence: float = 0.0


class WorkflowResult(BaseModel):
    task_id: str
    status: str
    entity_result: EntityResult | None = None
    event_result: EventResult | None = None
    ticker_links: TickerLinks | None = None
    market_metrics: MarketMetrics | None = None
    risk_result: RiskResult | None = None
    compliance_result: ComplianceResult | None = None
    report: str = ""
    error_message: str | None = None


class NewsItem(BaseModel):
    index: int | None = None
    title: str
    title_zh: str = ""
    content: str = ""
    content_zh: str = ""
    source: str = ""
    url: str = ""
    published_at: str = ""
    fetched_at: str = ""
    provider: str = ""
    relevance_score: float = 0
    relevance_reasons: list[str] = Field(default_factory=list)
    matched_tickers: list[str] = Field(default_factory=list)
    matched_topics: list[str] = Field(default_factory=list)
    matched_events: list[str] = Field(default_factory=list)
    source_weight: float = 0.5
    freshness_score: float = 0.0
    negative_score: float = 0.0
    negative_reasons: list[str] = Field(default_factory=list)


class SearchNewsRequest(BaseModel):
    query: str
    limit: int = 5
    language: str = "en"
    translate_to_zh: bool = True


class SearchNewsResponse(BaseModel):
    items: list[NewsItem] = Field(default_factory=list)


class BatchAnalyzeNewsRequest(BaseModel):
    query: str
    limit: int = 3
    language: str = "en"
    translate_to_zh: bool = True


class NewsAnalysisItem(BaseModel):
    news: NewsItem
    analysis_result: WorkflowResult | None = None
    status: str = "completed"
    error_message: str | None = None


class BatchAnalyzeNewsResponse(BaseModel):
    query: str
    total: int
    results: list[NewsAnalysisItem] = Field(default_factory=list)


class SearchAndAnalyzeRequest(BaseModel):
    query: str
    limit: int = 5
    language: str = "en"


class SearchAndAnalyzeResponse(BaseModel):
    selected_news: NewsItem | None = None
    analysis_result: WorkflowResult | None = None
    message: str = ""


class DailyBriefRequest(BaseModel):
    queries: list[str] = Field(
        default_factory=lambda: [
            "Nvidia AI chips",
            "Tesla robotaxi",
            "Federal Reserve interest rates",
            "Microsoft OpenAI",
        ]
    )
    limit_per_query: int = 3
    language: str = "en"
    translate_to_zh: bool = True
    max_items: int = 10


class TickerTrend(BaseModel):
    ticker: str
    direction: str
    confidence: float
    impact_score: float
    risk_level: str
    news_count: int
    reasons: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    source_titles: list[str] = Field(default_factory=list)


class DailyNewsAnalysis(BaseModel):
    news: NewsItem
    analysis_result: WorkflowResult | None = None
    status: str = "completed"
    error_message: str | None = None


class DailyBriefResponse(BaseModel):
    status: str
    queries: list[str] = Field(default_factory=list)
    total_news: int
    analyzed_news: list[DailyNewsAnalysis] = Field(default_factory=list)
    trends: list[TickerTrend] = Field(default_factory=list)
    report: str = ""
    error_message: str | None = None


class MarketPulseRequest(BaseModel):
    limit: int = 50
    language: str = "en"
    translate_to_zh: bool = False
    max_items: int = 5


class FinancialRecommendation(BaseModel):
    ticker: str
    recommendation_type: str
    direction: str
    confidence: float
    risk_level: str
    time_window: str
    rationale: str
    watch_points: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)


class MarketPulseResponse(BaseModel):
    status: str
    total_news: int
    candidate_news_count: int = 0
    filtered_news_count: int = 0
    analyzed_news_count: int = 0
    analyzed_news: list[DailyNewsAnalysis] = Field(default_factory=list)
    trends: list[TickerTrend] = Field(default_factory=list)
    recommendations: list[FinancialRecommendation] = Field(default_factory=list)
    report: str = ""
    error_message: str | None = None
