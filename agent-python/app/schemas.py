from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


DISCLAIMER = "This report is for market research only and is not investment advice."


class NewsItem(BaseModel):
    """Raw normalized news item flowing into the agent."""

    title: str = Field(description="News headline.")
    summary: str = Field(default="", description="Short article summary or snippet.")
    url: str = Field(default="", description="Canonical source URL.")
    source: str = Field(default="", description="Publisher or feed name.")
    published_at: str = Field(default="", description="Publication timestamp from source.")
    symbol: str | None = Field(default=None, description="Primary ticker or market symbol.")


class RankedNewsItem(NewsItem):
    """News item after deterministic relevance and impact ranking."""

    impact_score: float = Field(default=0.0, description="Deterministic impact score.")
    reason: str = Field(default="", description="Human-readable ranking explanation.")
    risk: str = Field(default="low", description="Observed risk level: low, medium, or high.")
    confidence: float = Field(default=0.0, description="Ranking confidence from 0 to 1.")


class MarketSignal(BaseModel):
    """Structured LLM/heuristic analysis for a ranked item."""

    title: str = Field(description="Signal headline.")
    summary: str = Field(description="Concise market observation.")
    url: str = Field(default="", description="Evidence URL.")
    source: str = Field(default="", description="Evidence source.")
    published_at: str = Field(default="", description="Evidence timestamp.")
    symbol: str | None = Field(default=None, description="Related ticker or symbol.")
    impact_score: float = Field(default=0.0, description="Observed impact intensity.")
    reason: str = Field(default="", description="Why the item matters.")
    risk: str = Field(default="low", description="Risk observation.")
    confidence: float = Field(default=0.0, description="Analysis confidence from 0 to 1.")


class AgentState(BaseModel):
    """Typed state passed between workflow nodes."""

    query: str = ""
    tickers: list[str] = Field(default_factory=list)
    max_items: int = 8
    trace_id: str = ""
    raw_news: list[NewsItem] = Field(default_factory=list)
    ranked_news: list[RankedNewsItem] = Field(default_factory=list)
    signals: list[MarketSignal] = Field(default_factory=list)
    report: AnalysisReport | None = None
    errors: list[str] = Field(default_factory=list)
    trace_path: str | None = None


class AnalysisReport(BaseModel):
    """Final market brief returned by the API."""

    trace_id: str
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    query: str = ""
    total_news: int = 0
    analyzed_news_count: int = 0
    risk: str = "low"
    confidence: float = 0.0
    summary: str = ""
    signals: list[MarketSignal] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER


class EvalCase(BaseModel):
    """Offline ranking test case with an expected importance label."""

    title: str
    summary: str = ""
    symbol: str | None = None
    expected_important: bool
    source: str = "offline_eval"
    url: str = ""
    published_at: str = ""


class EvalResult(BaseModel):
    """Persisted output of an offline eval run."""

    generated_at: str
    metrics: dict[str, float]
    ranked_titles: list[str]
    average_latency_ms: float
    cases: list[dict[str, Any]] = Field(default_factory=list)

