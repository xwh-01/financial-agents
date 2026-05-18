from schemas.request import AnalyzeRequest
from schemas.event import EventResult
from schemas.ticker import TickerLinks
from schemas.risk import RiskResult


RISK_KEYWORDS = [
    "lawsuit",
    "fraud",
    "investigation",
    "ban",
    "delay",
    "controversy",
    "scandal",
    "tariff",
    "regulation",
    "sec",
]


def check_risk(
    request: AnalyzeRequest,
    event_result: EventResult,
    ticker_links: TickerLinks,
) -> RiskResult:
    flags: list[str] = []

    source = request.source.lower().strip()
    if source in {"twitter", "x", "social_media", "reddit"}:
        flags.append("social_media_or_unverified_source")

    if event_result.confidence < 0.6 or ticker_links.confidence < 0.6:
        flags.append("low_confidence")

    if event_result.sentiment == "negative":
        flags.append("negative_sentiment")

    if event_result.impact_score >= 0.8:
        flags.append("high_impact_event")

    text = f"{request.title} {request.content}".lower()
    if any(keyword in text for keyword in RISK_KEYWORDS):
        flags.append("risk_keyword_detected")

    flags = _dedupe(flags)
    risk_level = _risk_level(flags, event_result.sentiment)

    return RiskResult(
        risk_level=risk_level,
        risk_flags=flags,
        reason=_build_reason(risk_level, flags),
    )


def _risk_level(flags: list[str], sentiment: str) -> str:
    if len(flags) >= 3:
        return "high"

    if len(flags) >= 1:
        return "medium"

    if sentiment == "negative":
        return "medium"

    return "low"


def _build_reason(risk_level: str, flags: list[str]) -> str:
    if risk_level == "low":
        return "当前事件未发现明显来源、置信度或负面舆情风险。"

    if risk_level == "medium":
        return f"当前事件存在一定风险，主要风险包括：{', '.join(flags)}。"

    return f"当前事件存在较高风险，多个风险因素同时出现：{', '.join(flags)}。"


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result