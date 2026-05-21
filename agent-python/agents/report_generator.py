# Legacy compatibility module. New code should use market_pulse.analyzers.

from market_pulse.analyzers.report_generator import generate_report

__all__ = ["generate_report"]
