from pydantic import BaseModel, Field

from schemas.news import NewsItem
from schemas.workflow import WorkflowResult


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
    limit: int = 20
    language: str = "en"
    translate_to_zh: bool = True
    max_items: int = 12


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
    analyzed_news: list[DailyNewsAnalysis] = Field(default_factory=list)
    trends: list[TickerTrend] = Field(default_factory=list)
    recommendations: list[FinancialRecommendation] = Field(default_factory=list)
    report: str = ""
    error_message: str | None = None
