import json
import re
from typing import Any

from market_pulse.schemas import AnalyzeRequest, EntityResult, EventResult
from clients.llm_client import chat_completion


EVENT_SYSTEM_PROMPT = """
你是一个金融舆情事件分析助手。

你必须只输出 JSON，不要输出 Markdown，不要输出解释，不要输出代码块。

任务：
根据新闻内容和已识别实体，判断事件类型、摘要、情绪、影响强度和置信度。

输出 JSON 格式必须严格如下：
{
  "event_type": "product_plan",
  "summary": "Elon Musk 提到 Tesla robotaxi 计划可能加速。",
  "sentiment": "positive",
  "impact_score": 0.7,
  "confidence": 0.85
}

event_type 只能取以下值之一：
- product_plan
- industry_demand
- partnership
- regulation_risk
- controversy
- earnings
- macro_policy
- unknown

sentiment 只能取以下值之一：
- positive
- negative
- neutral

要求：
1. 只输出 JSON object。
2. summary 使用中文，不超过 80 个中文字符。
3. impact_score 必须是 0 到 1 的数字。
4. confidence 必须是 0 到 1 的数字。
5. 不要输出投资建议。
6. 不要把相关性说成因果关系。
"""


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


def build_event_user_prompt(title: str, content: str, entity_result: dict) -> str:
    return f"""
请分析以下新闻事件。

标题：
{title}

正文：
{content}

已识别实体：
{entity_result}

只输出 JSON。
"""


def parse_llm_json(raw: str) -> dict[str, Any]:
    if not raw or not raw.strip():
        raise ValueError("LLM returned empty content")

    text = raw.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        raise ValueError("LLM JSON result is not an object")
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"Cannot find JSON object in LLM output: {raw[:300]}")

    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("Extracted JSON result is not an object")

    return data


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        num = float(value)
    except Exception:
        return default

    return max(0.0, min(1.0, num))


def as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()
