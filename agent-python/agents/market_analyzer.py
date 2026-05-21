# Legacy compatibility module. New code should use market_pulse.analyzers.

from market_pulse.analyzers.market_analyzer import analyze_market

__all__ = ["analyze_market"]
