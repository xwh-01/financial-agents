from collections.abc import Awaitable, Callable
from typing import Any

from reports.guard import apply_report_guard


State = dict[str, Any]
ToolFunc = Callable[[State], Awaitable[State]]
AGENT_FORBIDDEN_PHRASES = [
    "稳赚",
    "保证收益",
    "建议买入",
    "必须买入",
    "strong buy",
    "guaranteed return",
]


async def _call_node(state: State, node: Callable[[State], Any]) -> State:
    update = node(state)
    if hasattr(update, "__await__"):
        update = await update
    if update:
        state.update(update)
    return state


async def tool_collect_news(state: State) -> State:
    from market_pulse.nodes.collect_news import collect_news_node

    return await _call_node(state, collect_news_node)


async def tool_rank_news(state: State) -> State:
    from market_pulse.nodes.rank_news import rank_news_node

    return await _call_node(state, rank_news_node)


async def tool_analyze_items(state: State) -> State:
    from market_pulse.nodes.analyze_items import analyze_items_node

    return await _call_node(state, analyze_items_node)


async def tool_risk_route(state: State) -> State:
    from market_pulse.nodes.risk_review import risk_route_node

    return await _call_node(state, risk_route_node)


async def tool_risk_review(state: State) -> State:
    from market_pulse.nodes.risk_review import risk_review_node

    await tool_risk_route(state)
    await _call_node(state, risk_review_node)
    state["risk_review_checked"] = True
    return state


async def tool_generate_report(state: State) -> State:
    from market_pulse.nodes.generate_report import generate_report_node

    return await _call_node(state, generate_report_node)


async def tool_compliance_guard(state: State) -> State:
    result = state.get("result")
    if not isinstance(result, dict):
        state["compliance_checked"] = False
        state["error_message"] = "compliance_guard skipped because result is missing"
        return state

    guarded_result = apply_report_guard(result)
    _sanitize_agent_forbidden_phrases(guarded_result)
    state["result"] = guarded_result
    state["compliance_checked"] = True
    return state


def _sanitize_agent_forbidden_phrases(result: State) -> None:
    matched: list[str] = []
    for field in ("report", "summary"):
        text = result.get(field)
        if not isinstance(text, str):
            continue
        sanitized = text
        for phrase in AGENT_FORBIDDEN_PHRASES:
            if phrase.lower() in sanitized.lower():
                matched.append(phrase)
                sanitized = _replace_case_insensitive(sanitized, phrase, "[removed by compliance guard]")
        result[field] = sanitized

    if matched:
        warnings = list(result.get("compliance_warnings") or [])
        warnings.append(f"agent_forbidden_terms_removed: {', '.join(dict.fromkeys(matched))}")
        result["compliance_warnings"] = warnings
        result["compliance_status"] = "unsafe"


def _replace_case_insensitive(text: str, needle: str, replacement: str) -> str:
    lower_text = text.lower()
    lower_needle = needle.lower()
    start = 0
    chunks: list[str] = []

    while True:
        index = lower_text.find(lower_needle, start)
        if index == -1:
            chunks.append(text[start:])
            return "".join(chunks)
        chunks.append(text[start:index])
        chunks.append(replacement)
        start = index + len(needle)
