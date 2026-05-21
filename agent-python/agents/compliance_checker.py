# Legacy compatibility module. New code should use market_pulse.analyzers.

from market_pulse.analyzers.compliance_checker import check_compliance

__all__ = ["check_compliance"]
