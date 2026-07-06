import re
from copy import deepcopy
from typing import Any


DISCLAIMER = "本报告仅用于信息整理和研究参考，不构成投资建议。"

FORBIDDEN_REPLACEMENTS: dict[str, str] = {
    "建议买入": "可作为研究观察对象",
    "建议卖出": "需关注风险变化",
    "推荐买入": "可作为研究观察对象",
    "推荐卖出": "需关注风险变化",
    "强烈推荐买入": "信号值得进一步研究",
    "买入": "观察",
    "卖出": "风险观察",
    "strong buy": "market signal",
    "buy recommendation": "market signal",
    "sell recommendation": "risk observation",
    "investment advice": "research reference",
    "一定上涨": "存在上行可能但不确定",
    "一定下跌": "存在下行风险但不确定",
    "必涨": "存在上行可能但不确定",
    "必跌": "存在下行风险但不确定",
    "稳赚": "收益不确定",
    "保证收益": "收益不确定",
    "无风险": "风险需复核",
}

_FORBIDDEN_PATTERNS = [
    re.compile(re.escape(phrase), re.IGNORECASE)
    for phrase in sorted(FORBIDDEN_REPLACEMENTS, key=len, reverse=True)
]


def sanitize_text(text: str) -> tuple[str, list[str]]:
    sanitized = text or ""
    violations: list[str] = []

    for pattern in _FORBIDDEN_PATTERNS:
        replacement = FORBIDDEN_REPLACEMENTS.get(pattern.pattern.replace("\\", ""), "")
        if pattern.search(sanitized):
            violations.append(pattern.pattern.replace("\\", ""))
            sanitized = pattern.sub(replacement, sanitized)

    return sanitized, _dedupe(violations)


def apply_output_compliance_guard(result: dict[str, Any]) -> dict[str, Any]:
    guarded = deepcopy(result)
    violations: list[str] = []

    report, report_violations = sanitize_text(str(guarded.get("report") or ""))
    violations.extend(report_violations)
    if DISCLAIMER not in report:
        report = report.rstrip() + "\n\n免责声明：" + DISCLAIMER
    guarded["report"] = report

    guarded_signals = []
    for signal in guarded.get("market_signals") or []:
        checked_signal, signal_violations = sanitize_market_signal(signal)
        violations.extend(signal_violations)
        guarded_signals.append(checked_signal)
    guarded["market_signals"] = guarded_signals

    violations = _dedupe(violations)
    guarded["compliance_status"] = "warning" if violations else "safe"
    guarded["compliance_violations"] = violations
    guarded["disclaimer"] = DISCLAIMER
    return guarded


def sanitize_market_signal(signal: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    checked = dict(signal)
    violations: list[str] = []

    for key in ("title", "summary", "risk_reason", "uncertainty", "evidence_summary"):
        sanitized, key_violations = sanitize_text(str(checked.get(key) or ""))
        checked[key] = sanitized
        violations.extend(key_violations)

    if violations:
        checked["compliance_violation"] = True
        checked["signal_type"] = "risk_observation"
        checked["risk_level"] = _escalate_risk(str(checked.get("risk_level") or "low"))
        uncertainty = str(checked.get("uncertainty") or "").strip()
        note = "已检测到可能构成投资建议或确定性预测的表达，已改写为中性风险观察。"
        checked["uncertainty"] = f"{uncertainty} {note}".strip()
    else:
        checked["compliance_violation"] = False

    return checked, _dedupe(violations)


def compliance_violation_rate(items: list[dict[str, Any]]) -> float:
    if not items:
        return 0.0
    flagged = sum(1 for item in items if item.get("compliance_violation"))
    return round(flagged / len(items), 4)


def _escalate_risk(value: str) -> str:
    return "high" if value == "high" else "medium"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
