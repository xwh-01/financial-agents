import json
import re
from typing import Any

from market_pulse.schemas import AnalyzeRequest, EntityResult
from clients.llm_client import chat_completion


ENTITY_SYSTEM_PROMPT = """
你是一个金融舆情实体识别助手。

你必须只输出 JSON，不要输出 Markdown，不要输出解释，不要输出代码块。

任务：
从新闻标题和正文中识别金融相关实体。

输出 JSON 格式必须严格如下：
{
  "persons": ["Elon Musk"],
  "companies": ["Tesla"],
  "tickers": ["TSLA"],
  "topics": ["robotaxi", "autonomous driving"],
  "confidence": 0.85
}

字段说明：
- persons: 公众人物英文标准名列表
- companies: 公司或组织英文标准名列表
- tickers: 股票代码列表，使用大写美股 ticker
- topics: 主题关键词列表，使用英文短语
- confidence: 0 到 1 之间的小数

要求：
1. 只输出 JSON object。
2. 不要输出 ```json。
3. 不要输出解释文字。
4. 如果没有识别到内容，对应数组为空。
5. confidence 必须是数字。
"""


async def resolve_entities(request: AnalyzeRequest) -> EntityResult:
    user_prompt = build_entity_user_prompt(request.title, request.content)
    raw = await chat_completion(ENTITY_SYSTEM_PROMPT, user_prompt)
    data = parse_llm_json(raw)

    return EntityResult(
        persons=as_str_list(data.get("persons")),
        companies=as_str_list(data.get("companies")),
        tickers=[ticker.upper() for ticker in as_str_list(data.get("tickers"))],
        topics=as_str_list(data.get("topics")),
        confidence=as_float(data.get("confidence"), default=0.0),
    )


def build_entity_user_prompt(title: str, content: str) -> str:
    return f"""
请识别以下新闻中的金融相关实体。

标题：
{title}

正文：
{content}

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


def as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    result: list[str] = []
    seen = set()

    for item in value:
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)

    return result


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        num = float(value)
    except Exception:
        return default

    return max(0.0, min(1.0, num))
