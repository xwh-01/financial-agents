from typing import Literal

from market_pulse.state import MarketPulseGraphState
from market_pulse.trace import record_skipped_report_step


def risk_route_node(
    state: MarketPulseGraphState,
) -> MarketPulseGraphState:
    """
    Explicit graph step before conditional routing.

    This node exists so that the risk routing decision appears as a distinct step
    in the trace, rather than being an invisible conditional edge. It is a no-op
    — route_after_risk (below) performs the actual conditional branching.
    """
    print("[langgraph-market] risk_route")
    return {}


def route_after_risk(
    state: MarketPulseGraphState,
) -> Literal["risk_review", "generate_report"]:
    """
    Conditional routing: if overall_risk_level is "high", go through risk_review
    to collect human-readable risk notes. Otherwise skip directly to generate_report.

    When skipping, we record a "skipped" event in the trace for observability.
    """
    if state.get("overall_risk_level") == "high":
        return "risk_review"
    record_skipped_report_step(state, "risk_review", "overall_risk_level was not high")
    return "generate_report"


def risk_review_node(state: MarketPulseGraphState) -> MarketPulseGraphState:
    """
    Collect risk observations from high-risk analysis results.

    Only executed when overall_risk_level == "high". Gathers:
      - Reasons from high-risk items (e.g. "检测到诉讼关键词")
      - Compliance violations that failed the safety guard

    These notes are appended to the final report so high-risk outputs get
    human-visible disclaimers.
    """
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
