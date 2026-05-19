from pydantic import BaseModel

from schemas.entity import EntityResult
from schemas.event import EventResult
from schemas.ticker import TickerLinks
from schemas.market import MarketMetrics
from schemas.risk import RiskResult
from schemas.compliance import ComplianceResult


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
