"""Report compliance guard: block unsafe investment advice expressions."""
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "本报告由 AI 基于公开新闻信息生成，"
    "仅用于信息整理、研究参考和风险提示，"
    "不构成任何投资建议、买卖建议或收益承诺。"
    "投资有风险，用户应自行判断并承担决策责任。"
)

_UNSAFE_PATTERNS: dict[str, str] = {
    r"建议买入": "unsafe",
    r"建议卖出": "unsafe",
    r"强烈推荐买入": "unsafe",
    r"必须买入": "unsafe",
    r"必涨": "unsafe",
    r"稳赚": "unsafe",
    r"保证收益": "unsafe",
    r"无风险": "unsafe",
    r"目标价一定达到": "unsafe",
    r"马上入场": "unsafe",
    r"抄底": "unsafe",
    r"梭哈": "unsafe",
    r"满仓": "unsafe",
    r"investment advice": "unsafe",
    r"buy recommendation": "unsafe",
    r"sell recommendation": "unsafe",
    r"guaranteed return": "unsafe",
    r"risk-free": "unsafe",
    r"must buy": "unsafe",
    r"strong buy": "unsafe",
}

_SAFE_PATTERNS: list[str] = [
    r"值得关注",
    r"后续观察",
    r"可能影响",
    r"风险提示",
    r"信息参考",
    r"不构成投资建议",
]


def scan_unsafe_text(text: str) -> dict[str, Any]:
    matched: list[str] = []
    risk_level = "safe"

    for pattern, level in _UNSAFE_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            matched.append(pattern)
            if level == "unsafe":
                risk_level = "unsafe"
            elif risk_level != "unsafe" and level == "warning":
                risk_level = "warning"

    return {
        "is_unsafe": risk_level != "safe",
        "matched_terms": matched,
        "risk_level": risk_level,
    }


def apply_report_guard(report_result: dict) -> dict[str, Any]:
    overall_risk = "safe"
    all_matched: list[str] = []
    warnings: list[str] = []

    try:
        summary_text = str(report_result.get("summary") or report_result.get("report") or "")
        if summary_text:
            scan = scan_unsafe_text(summary_text)
            all_matched.extend(scan["matched_terms"])
            overall_risk = _escalate(overall_risk, scan["risk_level"])

        analyzed = report_result.get("analyzed_news") or report_result.get("analyzed_items") or []
        for entry in analyzed:
            news = entry.get("news") or {}
            analysis = entry.get("analysis_result") or {}
            entry_text = (
                (news.get("title") or "")
                + " "
                + str(analysis.get("report") or "")
            )
            if entry_text.strip():
                scan = scan_unsafe_text(entry_text)
                all_matched.extend(scan["matched_terms"])
                overall_risk = _escalate(overall_risk, scan["risk_level"])

    except Exception:
        logger.warning("guard scan failed, attaching disclaimer only", exc_info=True)
        overall_risk = "warning"

    if all_matched:
        unique = list(dict.fromkeys(all_matched))
        warnings.append(f"matched_unsafe_terms: {', '.join(unique)}")

    compliance_status = overall_risk if overall_risk != "safe" else "safe"

    result = dict(report_result)
    result["compliance_status"] = compliance_status
    result["compliance_warnings"] = warnings
    result["disclaimer"] = DISCLAIMER
    return result


def append_disclaimer(text: str) -> str:
    if not text:
        return DISCLAIMER
    return f"{text}\n\n{DISCLAIMER}"


def _escalate(current: str, incoming: str) -> str:
    order = {"safe": 0, "warning": 1, "unsafe": 2}
    if order.get(incoming, 0) > order.get(current, 0):
        return incoming
    return current
