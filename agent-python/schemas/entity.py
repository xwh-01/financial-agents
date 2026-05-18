from pydantic import BaseModel, Field


class EntityResult(BaseModel):
    persons: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    tickers: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    confidence: float = 0.0