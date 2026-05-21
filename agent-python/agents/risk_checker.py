# Legacy compatibility module. New code should use market_pulse.analyzers.

from market_pulse.analyzers.risk_checker import check_risk

__all__ = ["check_risk"]
