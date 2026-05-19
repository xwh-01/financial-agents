from pydantic import BaseModel


class EventResult(BaseModel):
    event_type: str
    summary: str
    sentiment: str
    impact_score: float
    confidence: float
