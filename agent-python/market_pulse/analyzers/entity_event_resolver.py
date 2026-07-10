"""Merged entity resolution + event analysis + risk assessment in one LLM call.

Replaces three separate steps (resolve_entities, analyze_event, check_risk)
with a single structured LLM invocation.
"""

import json
import re
from typing import Any

from clients.llm_client import chat_completion
from market_pulse.schemas import AnalyzeRequest, EntityResult, EventResult, RiskResult


ENTITY_EVENT_SYSTEM_PROMPT = """
你是一个金融舆情分析助手。

你必须只输出 JSON，不要输出 Markdown，不要输出解释，不要输出代码块。

任务：
从新闻标题和正文中提取金融实体、分析事件、判断风险。

输出 JSON 格式必须严格如下：
{
  "persons": ["Jensen Huang"],
  "companies": ["Nvidia"],
  "tickers": ["NVDA"],
  "topics": ["earnings", "AI chip", "data center"],
  "entity_confidence": 0.85,
  "event_type": "earnings",
  "summary": "英伟达公布创纪录季度财报，数据中心营收超预期",
  "sentiment": "positive",
  "impact_score": 0.85,
  "event_confidence": 0.90,
  "risk_level": "medium",
  "risk_flags": ["high_impact_event"]
}

字段说明：
- persons: 公众人物英文标准名列表
- companies: 公司或组织英文标准名列表
- tickers: 股票代码列表，使用大写美股 ticker
- topics: 主题关键词列表，使用英文短语
- entity_confidence: 实体识别置信度，0-1

- event_type: product_plan / industry_demand / partnership / regulation_risk /
             controversy / earnings / macro_policy / unknown
- summary: 中文摘要，不超过 80 个中文字符
- sentiment: positive / negative / neutral
- impact_score: 事件影响强度，0-1
- event_confidence: 事件分析置信度，0-1

- risk_level: low / medium / high
  判断依据: 综合考虑事件性质(财报/争议/政策...)、情绪方向、影响强度、
  是否涉及高波动性标的、是否存在监管/诉讼/延迟等风险因素。
  - low: 常规运营、行业需求报告等中性或低影响事件
  - medium: 财报公布、产品计划、合作伙伴等有一定不确定性的事件
  - high: 涉及诉讼、调查、重大争议、监管干预、供应链断裂等高风险事件

- risk_flags: 风险标记列表，可选值:
  social_media_source, low_confidence, negative_sentiment, high_impact,
  regulatory_concern, litigation_risk, supply_chain_risk, geopolitical_risk,
  earnings_volatility, macro_uncertainty

要求：
1. 只输出 JSON object。
2. 不要输出 ```json。
3. 不要输出解释文字。
4. 如果没有识别到内容，对应数组为空。
5. confidence 必须是数字。
6. 不要把相关性说成因果关系。
7. 不要输出投资建议。
"""

VALID_EVENT_TYPES = frozenset({
    "product_plan", "industry_demand", "partnership", "regulation_risk",
    "controversy", "earnings", "macro_policy", "unknown",
})

VALID_SENTIMENTS = frozenset({"positive", "negative", "neutral"})

VALID_RISK_LEVELS = frozenset({"low", "medium", "high"})

VALID_RISK_FLAGS = frozenset({
    "social_media_source", "low_confidence", "negative_sentiment",
    "high_impact", "regulatory_concern", "litigation_risk",
    "supply_chain_risk", "geopolitical_risk",
    "earnings_volatility", "macro_uncertainty",
})


async def resolve_entity_and_event(request: AnalyzeRequest) -> tuple[EntityResult, EventResult, RiskResult]:
    """
    Extract entities, classify the event, and assess risk — all in a single LLM call.

    This is the preferred path that replaces the older three-step approach
    (resolve_entities -> analyze_event -> check_risk) with one structured
    invocation. The LLM returns a single JSON object containing all three
    result types. Each field is validated against an allowlist (event types,
    sentiments, risk levels, risk flags) and sanitized on parse failure.

    Returns:
      EntityResult  — persons, companies, tickers, topics, confidence
      EventResult   — event_type, sentiment, impact_score, summary, confidence
      RiskResult    — risk_level, risk_flags, reason
    """
    user_prompt = _build_user_prompt(request.title, request.content)
    raw = await chat_completion(ENTITY_EVENT_SYSTEM_PROMPT, user_prompt)
    data = _parse_llm_json(raw)

    entity = EntityResult(
        persons=_as_str_list(data.get("persons")),
        companies=_as_str_list(data.get("companies")),
        tickers=[t.upper() for t in _as_str_list(data.get("tickers"))],
        topics=_as_str_list(data.get("topics")),
        confidence=_as_float(data.get("entity_confidence"), default=0.0),
    )

    event_type = _as_str(data.get("event_type"), default="unknown")
    if event_type not in VALID_EVENT_TYPES:
        event_type = "unknown"
    sentiment = _as_str(data.get("sentiment"), default="neutral")
    if sentiment not in VALID_SENTIMENTS:
        sentiment = "neutral"
    summary = _as_str(data.get("summary"), default="")
    if not summary:
        summary = "系统未能生成明确事件摘要。"

    event = EventResult(
        event_type=event_type,
        summary=summary,
        sentiment=sentiment,
        impact_score=_as_float(data.get("impact_score"), default=0.0),
        confidence=_as_float(data.get("event_confidence"), default=0.0),
    )

    risk_level = _as_str(data.get("risk_level"), default="low")
    if risk_level not in VALID_RISK_LEVELS:
        risk_level = "low"
    risk_flags = [
        f for f in _as_str_list(data.get("risk_flags"))
        if f in VALID_RISK_FLAGS
    ]

    risk = RiskResult(
        risk_level=risk_level,
        risk_flags=risk_flags,
        reason=_build_risk_reason(risk_level, risk_flags),
    )

    return entity, event, risk


def _build_user_prompt(title: str, content: str) -> str:
    return f"""
请识别以下新闻中的金融实体、分析事件、判断风险。

标题：
{title}

正文：
{content}

只输出 JSON。
"""


def _build_risk_reason(risk_level: str, flags: list[str]) -> str:
    if risk_level == "low":
        return "当前事件未发现明显风险因素。"
    if risk_level == "medium":
        flag_text = ", ".join(flags) if flags else "中等不确定性"
        return f"当前事件存在一定风险：{flag_text}。"
    flag_text = ", ".join(flags) if flags else "高风险事件"
    return f"当前事件存在较高风险：{flag_text}。"


def _parse_llm_json(raw: str) -> dict[str, Any]:
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


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        num = float(value)
    except Exception:
        return default
    return max(0.0, min(1.0, num))
