# Legacy compatibility module. New code should use market_pulse.analyzers.

from market_pulse.analyzers.event_analyzer import analyze_event

__all__ = ["analyze_event"]
