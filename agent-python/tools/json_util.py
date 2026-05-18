import json
import re
from typing import Any


def parse_llm_json(raw: str) -> dict[str, Any]:
    """
    尽量从 LLM 输出中提取 JSON。
    支持：
    1. 纯 JSON
    2. ```json ... ```
    3. 前后有解释文字，中间包含 JSON 对象
    """
    if not raw or not raw.strip():
        raise ValueError("LLM returned empty content")

    text = raw.strip()

    # 去掉 Markdown 代码块
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

    # 先尝试整体解析
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        raise ValueError("LLM JSON result is not an object")
    except json.JSONDecodeError:
        pass

    # 再尝试提取第一个 JSON object
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


def as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()