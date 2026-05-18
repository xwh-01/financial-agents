from schemas.request import AnalyzeRequest
from schemas.entity import EntityResult
from schemas.event import EventResult
from tools.llm_client import chat_completion
from tools.json_util import parse_llm_json, as_float, as_str
from prompts.event_prompt import EVENT_SYSTEM_PROMPT, build_event_user_prompt


VALID_EVENT_TYPES = {
    "product_plan",
    "industry_demand",
    "partnership",
    "regulation_risk",
    "controversy",
    "earnings",
    "macro_policy",
    "unknown",
}

VALID_SENTIMENTS = {"positive", "negative", "neutral"}


async def analyze_event(
    request: AnalyzeRequest,
    entity_result: EntityResult,
) -> EventResult:
    user_prompt = build_event_user_prompt(
        request.title,
        request.content,
        entity_result.model_dump(),
    )
    raw = await chat_completion(EVENT_SYSTEM_PROMPT, user_prompt)
    data = parse_llm_json(raw)

    event_type = as_str(data.get("event_type"), default="unknown")
    if event_type not in VALID_EVENT_TYPES:
        event_type = "unknown"

    sentiment = as_str(data.get("sentiment"), default="neutral")
    if sentiment not in VALID_SENTIMENTS:
        sentiment = "neutral"

    summary = as_str(data.get("summary"), default="")
    if not summary:
        summary = "系统未能生成明确事件摘要。"

    return EventResult(
        event_type=event_type,
        summary=summary,
        sentiment=sentiment,
        impact_score=as_float(data.get("impact_score"), default=0.0),
        confidence=as_float(data.get("confidence"), default=0.0),
    )