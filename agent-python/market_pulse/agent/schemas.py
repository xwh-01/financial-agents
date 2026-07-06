from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


ActionName = Literal[
    "collect_news",
    "rank_news",
    "analyze_items",
    "risk_review",
    "generate_report",
    "compliance_guard",
    "finish",
]

TraceStatus = Literal["running", "completed", "failed", "degraded"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentAction(BaseModel):
    name: ActionName
    reason: str


class AgentObservation(BaseModel):
    summary: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)


class AgentTraceStep(BaseModel):
    step_no: int
    action: AgentAction
    observation: AgentObservation
    metrics: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: str = Field(default_factory=utc_now_iso)


class AgentTraceRun(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    query: str
    tickers: list[str] = Field(default_factory=list)
    max_items: int = 8
    steps: list[AgentTraceStep] = Field(default_factory=list)
    final_result: dict[str, Any] | None = None
    status: TraceStatus = "running"
