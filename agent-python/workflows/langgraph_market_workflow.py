# Legacy compatibility module. New code should use market_pulse/...

from market_pulse.graph import langgraph_market_pulse, run_langgraph_market_pulse

__all__ = ["langgraph_market_pulse", "run_langgraph_market_pulse"]
