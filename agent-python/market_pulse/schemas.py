"""Market Pulse schema facade.

The first migration phase keeps the original Pydantic model files in
`schemas/` and centralizes Market Pulse imports through this module.
"""

from schemas.compliance import ComplianceResult
from schemas.entity import EntityResult
from schemas.event import EventResult
from schemas.market import MarketMetric, MarketMetrics
from schemas.news import (
    BatchAnalyzeNewsRequest,
    BatchAnalyzeNewsResponse,
    NewsAnalysisItem,
    NewsItem,
    SearchNewsRequest,
    SearchNewsResponse,
)
from schemas.report import ReportResult
from schemas.request import AnalyzeRequest
from schemas.risk import RiskResult
from schemas.search_analyze import SearchAndAnalyzeRequest, SearchAndAnalyzeResponse
from schemas.ticker import TickerLinks
from schemas.trend import (
    DailyBriefRequest,
    DailyBriefResponse,
    DailyNewsAnalysis,
    FinancialRecommendation,
    MarketPulseRequest,
    MarketPulseResponse,
    TickerTrend,
)
from schemas.workflow import WorkflowResult

__all__ = [
    "AnalyzeRequest",
    "BatchAnalyzeNewsRequest",
    "BatchAnalyzeNewsResponse",
    "ComplianceResult",
    "DailyBriefRequest",
    "DailyBriefResponse",
    "DailyNewsAnalysis",
    "EntityResult",
    "EventResult",
    "FinancialRecommendation",
    "MarketMetric",
    "MarketMetrics",
    "MarketPulseRequest",
    "MarketPulseResponse",
    "NewsAnalysisItem",
    "NewsItem",
    "ReportResult",
    "RiskResult",
    "SearchAndAnalyzeRequest",
    "SearchAndAnalyzeResponse",
    "SearchNewsRequest",
    "SearchNewsResponse",
    "TickerLinks",
    "TickerTrend",
    "WorkflowResult",
]
