# Legacy compatibility module. New code should use market_pulse.analyzers.

from market_pulse.analyzers.trend_predictor import (
    build_daily_trend_report,
    build_financial_recommendations,
    build_market_pulse_report,
    predict_ticker_trends,
)

__all__ = [
    "build_daily_trend_report",
    "build_financial_recommendations",
    "build_market_pulse_report",
    "predict_ticker_trends",
]
