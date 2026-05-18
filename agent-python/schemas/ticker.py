from pydantic import BaseModel, Field


class TickerLinks(BaseModel):
    direct_tickers: list[str] = Field(default_factory=list)
    related_tickers: list[str] = Field(default_factory=list)
    etfs: list[str] = Field(default_factory=list)
    reason: str = ""
    confidence: float = 0.0