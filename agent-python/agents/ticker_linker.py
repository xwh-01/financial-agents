# Legacy compatibility module. New code should use market_pulse.analyzers.

from market_pulse.analyzers.ticker_linker import link_tickers

__all__ = ["link_tickers"]
