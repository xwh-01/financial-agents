# Legacy compatibility module. New code should use clients.market_data_client.

from clients.market_data_client import (
    calculate_returns,
    fetch_market_history,
    normalize_market_data,
)

__all__ = ["calculate_returns", "fetch_market_history", "normalize_market_data"]
