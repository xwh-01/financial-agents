from typing import Literal

from market_pulse.state import MarketPulseGraphState
from market_pulse.trace import record_skipped_report_step


def risk_route_node(
    state: MarketPulseGraphState,
) -> MarketPulseGraphState:
    """Keep an explicit graph step before conditional high-risk routing."""
    print("[langgraph-market] risk_route")
    return {}


def route_after_risk(
    state: MarketPulseGraphState,
) -> Literal["risk_review", "generate_report"]:
    if state.get("overall_risk_level") == "high":
        return "risk_review"
    record_skipped_report_step(state, "risk_review", "overall_risk_level was not high")
    return "generate_report"


def risk_review_node(state: MarketPulseGraphState) -> MarketPulseGraphState:
    """Collect extra risk and compliance notes for high-risk results."""
    print("[langgraph-market] risk_review")
    notes: list[str] = []

    for item in state.get("analyzed_news", []):
        result = item.analysis_result
        if not result or not result.risk_result:
            continue

        if result.risk_result.risk_level == "high":
            notes.append(result.risk_result.reason)

        if result.compliance_result and not result.compliance_result.passed:
            notes.extend(result.compliance_result.violations)

    return {"risk_review_notes": _dedupe(notes)}


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result: list[str] = []

    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)

    return result
