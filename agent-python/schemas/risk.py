from pydantic import BaseModel, Field


class RiskResult(BaseModel):
    risk_level: str
    risk_flags: list[str] = Field(default_factory=list)
    reason: str