from pydantic import BaseModel, Field


class MarketMetric(BaseModel):
    return_1d: float | None = None
    return_3d: float | None = None
    return_7d: float | None = None
    volume_change: float | None = None
    relative_to_spy_3d: float | None = None


class MarketMetrics(BaseModel):
    metrics: dict[str, MarketMetric] = Field(default_factory=dict)
