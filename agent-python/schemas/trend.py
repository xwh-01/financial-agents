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
    # 多抓候选新闻，提高覆盖率
    limit: int = 50

    # 当前新闻源主要按英文搜索
    language: str = "en"

    # 不在搜索阶段翻译，否则会非常慢
    translate_to_zh: bool = False

    # 最多深度分析 5 条，避免一次请求跑太久
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

    # 本次真正进入深度分析的新闻数量
    total_news: int

    # 候选新闻池数量：从新闻 API 抓到并去重后的数量
    candidate_news_count: int = 0

    # 过滤排序后的新闻数量：ranker 认为值得关注的数量
    filtered_news_count: int = 0

    # 实际完成分析流程的新闻数量
    analyzed_news_count: int = 0

    analyzed_news: list[DailyNewsAnalysis] = Field(default_factory=list)
    trends: list[TickerTrend] = Field(default_factory=list)
    recommendations: list[FinancialRecommendation] = Field(default_factory=list)
    report: str = ""
    error_message: str | None = None