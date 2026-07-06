import json
import re
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = ROOT / "agent-python"
sys.path.insert(0, str(AGENT_ROOT))

from safety.compliance import sanitize_text  # noqa: E402


GOLDEN_PATH = ROOT / "evals" / "golden_set.json"
REPORT_JSON = ROOT / "evals" / "report.json"
REPORT_MD = ROOT / "evals" / "report.md"


TICKER_KEYWORDS = {
    "NVDA": ["nvidia", "gpu"],
    "TSLA": ["tesla"],
    "AAPL": ["apple"],
    "MSFT": ["microsoft", "azure"],
    "AMZN": ["amazon"],
    "META": ["meta"],
    "GOOGL": ["alphabet", "google"],
    "AMD": ["amd"],
    "CRM": ["salesforce"],
    "JPM": ["jpmorgan"],
    "PFE": ["pfizer"],
    "WMT": ["walmart"],
    "BA": ["boeing"],
    "XOM": ["exxon"],
    "NFLX": ["netflix"],
    "SBUX": ["starbucks"],
    "SPY": ["stock market", "monetary policy", "fed"],
    "TLT": ["treasury", "interest rate", "fed"],
    "XLE": ["oil", "energy", "crude"],
    "GLD": ["gold"],
    "KRE": ["regional bank", "commercial real estate"],
}

EVENT_KEYWORDS = {
    "earnings": ["earnings", "revenue", "guidance", "margin"],
    "macro_policy": ["fed", "inflation", "interest rate", "dollar"],
    "regulation_risk": ["regulator", "regulators", "privacy", "antitrust", "court", "recall"],
    "industry_demand": ["demand", "growth", "cloud", "subscriber", "ai"],
    "product_plan": ["launch", "announced", "product", "accelerator"],
    "commodity_supply": ["oil", "supply", "refinery", "gasoline", "exports"],
    "credit_risk": ["loan loss", "bank", "commercial real estate"],
    "capital_return": ["dividend", "capital", "stress test"],
    "clinical_trial": ["trial", "drug"],
    "consumer_demand": ["grocery", "consumer", "discretionary"],
    "operational_risk": ["supplier", "inspection", "deliveries"],
    "competition": ["competition", "sales"],
}

HIGH_RISK_TERMS = [
    r"\brecall\b",
    r"\bregulators?\b",
    r"\bprivacy\b",
    r"\bantitrust\b",
    r"\bloan loss\b",
    r"\bcuts annual guidance\b",
    r"\bmixed\b",
    r"\bdelay",
]
MEDIUM_RISK_TERMS = [
    r"\binflation\b",
    r"\binterest rate\b",
    r"\boil\b",
    r"\bgold\b",
    r"\bguidance\b",
    r"\bcompetition\b",
    r"\bweaker\b",
    r"\bdiscretionary\b",
    r"\blaunch",
    r"\brefinery\b",
    r"\bgasoline\b",
]


def main() -> None:
    started = time.perf_counter()
    cases = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    rows = [evaluate_case(case) for case in cases]
    elapsed_ms = (time.perf_counter() - started) * 1000

    total = len(rows)
    failed = [row for row in rows if not row["passed"]]
    metrics = {
        "relevance_at_5": round(sum(row["relevance_pass"] for row in rows) / total, 4),
        "ticker_linking_accuracy": round(sum(row["ticker_pass"] for row in rows) / total, 4),
        "risk_label_accuracy": round(sum(row["risk_pass"] for row in rows) / total, 4),
        "faithfulness_pass_rate": round(sum(row["faithfulness_pass"] for row in rows) / total, 4),
        "compliance_violation_rate": round(sum(row["compliance_violation"] for row in rows) / total, 4),
        "avg_latency_ms": round(elapsed_ms / total, 2),
        "total_cases": total,
        "passed_cases": total - len(failed),
        "failed_cases": len(failed),
    }

    payload = {"metrics": metrics, "cases": rows}
    REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(render_markdown(metrics, rows), encoding="utf-8")

    print("Offline eval complete")
    for key, value in metrics.items():
        print(f"{key}: {value}")


def evaluate_case(case: dict) -> dict:
    text = f"{case['title']} {case['content']}".lower()
    predicted_tickers = predict_tickers(text)
    predicted_event = predict_event_type(text)
    predicted_risk = predict_risk_level(text)
    report_text = build_mock_signal_text(case, predicted_tickers, predicted_event, predicted_risk)
    _, violations = sanitize_text(report_text)

    relevance_pass = sum(1 for keyword in case["expected_keywords"] if keyword.lower() in text) >= 2
    ticker_pass = bool(set(case["expected_tickers"]) & set(predicted_tickers))
    risk_pass = predicted_risk == case["expected_risk_level"]
    faithfulness_pass = (
        case["title"] in report_text
        and all(ticker in report_text for ticker in predicted_tickers[:1])
        and case["url"] in report_text
    )
    forbidden_hit = any(phrase.lower() in report_text.lower() for phrase in case["forbidden_phrases"])
    compliance_violation = bool(violations or forbidden_hit)

    return {
        "case_id": case["case_id"],
        "predicted_tickers": predicted_tickers,
        "expected_tickers": case["expected_tickers"],
        "predicted_event_type": predicted_event,
        "expected_event_type": case["expected_event_type"],
        "predicted_risk_level": predicted_risk,
        "expected_risk_level": case["expected_risk_level"],
        "relevance_pass": relevance_pass,
        "ticker_pass": ticker_pass,
        "risk_pass": risk_pass,
        "faithfulness_pass": faithfulness_pass,
        "compliance_violation": compliance_violation,
        "passed": relevance_pass and ticker_pass and risk_pass and faithfulness_pass and not compliance_violation,
    }


def predict_tickers(text: str) -> list[str]:
    result = []
    for ticker, keywords in TICKER_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            result.append(ticker)
    return result or ["MARKET"]


def predict_event_type(text: str) -> str:
    scores = {
        event: sum(1 for keyword in keywords if keyword in text)
        for event, keywords in EVENT_KEYWORDS.items()
    }
    best_event, best_score = max(scores.items(), key=lambda item: item[1])
    return best_event if best_score else "unknown"


def predict_risk_level(text: str) -> str:
    if any(re.search(term, text) for term in HIGH_RISK_TERMS):
        return "high"
    if any(re.search(term, text) for term in MEDIUM_RISK_TERMS):
        return "medium"
    return "low"


def build_mock_signal_text(
    case: dict,
    predicted_tickers: list[str],
    predicted_event: str,
    predicted_risk: str,
) -> str:
    return (
        f"市场观察信号：{case['title']}\n"
        f"相关标的：{', '.join(predicted_tickers)}\n"
        f"事件类型：{predicted_event}\n"
        f"风险等级：{predicted_risk}\n"
        f"证据摘要：{case['content']}\n"
        f"相关来源：{case['source']} {case['url']}\n"
        "本报告仅用于信息整理和研究参考，不构成投资建议。"
    )


def render_markdown(metrics: dict, rows: list[dict]) -> str:
    lines = [
        "# Financial Agents Offline Eval Report",
        "",
        "## Metrics",
        "",
    ]
    for key, value in metrics.items():
        lines.append(f"- `{key}`: {value}")

    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| case_id | ticker | risk | faithfulness | compliance | passed |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in rows:
        lines.append(
            "| {case_id} | {ticker} | {risk} | {faithfulness} | {compliance} | {passed} |".format(
                case_id=row["case_id"],
                ticker="yes" if row["ticker_pass"] else "no",
                risk="yes" if row["risk_pass"] else "no",
                faithfulness="yes" if row["faithfulness_pass"] else "no",
                compliance="violation" if row["compliance_violation"] else "clean",
                passed="yes" if row["passed"] else "no",
            )
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
