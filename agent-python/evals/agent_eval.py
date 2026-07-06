"""Offline eval for MarketPulseDirectorAgent.

Usage:
  cd agent-python
  python evals/agent_eval.py
"""
import asyncio
import base64
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_pulse.agent.runner import MarketPulseAgentRunner
from market_pulse.agent.tools import tool_compliance_guard


BASE_DIR = Path(__file__).resolve().parent
CASES_PATH = BASE_DIR / "agent_eval_cases.yaml"
REPORT_PATH = BASE_DIR / "reports" / "agent_eval_report.md"


async def main() -> None:
    cases = yaml.safe_load(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    rows = []

    for case in cases:
        trace = await _run_case(case)
        actions = [step.action.name for step in trace.steps if step.action.name != "finish"]
        checks = _evaluate_case(case, trace, actions)
        rows.append(
            {
                "case": case["id"],
                "expected": checks["expected"],
                "actual": checks["actual"],
                "passed": checks["passed"],
                "notes": checks["notes"],
            }
        )

    _write_report(rows)
    passed = sum(1 for row in rows if row["passed"])
    print(f"Market Pulse agent eval: {passed}/{len(rows)} passed")
    print(f"Report written to {REPORT_PATH}")


async def _run_case(case: dict[str, Any]):
    tools = {
        "collect_news": _tool_collect_news(case),
        "rank_news": _tool_rank_news,
        "analyze_items": _tool_analyze_items(case),
        "risk_review": _tool_risk_review,
        "generate_report": _tool_generate_report(case),
        "compliance_guard": tool_compliance_guard,
    }
    runner = MarketPulseAgentRunner(tools=tools, save_traces=False)
    return await runner.run(
        query=case["query"],
        max_items=case.get("max_items", 4),
        tickers=case.get("tickers", []),
        max_steps=10,
    )


def _tool_collect_news(case: dict[str, Any]):
    async def tool(state: dict[str, Any]) -> dict[str, Any]:
        if case.get("empty_news"):
            state["candidate_news"] = []
            state["error_message"] = "External news source returned no items."
            return state

        tickers = state.get("tickers") or ["MARKET"]
        state["candidate_news"] = [
            {
                "title": f"{ticker} market pulse item {index}",
                "content": "Public news summary for market research.",
                "source": "Example News",
                "source_url": f"https://example.com/{ticker.lower()}/{index}",
                "source_metadata": {"provider": "offline_eval", "ticker": ticker},
            }
            for index, ticker in enumerate((tickers * 3)[:4], start=1)
        ]
        return state

    return tool


async def _tool_rank_news(state: dict[str, Any]) -> dict[str, Any]:
    ranked = list(state.get("candidate_news") or [])
    state["ranked_news"] = ranked
    state["selected_news"] = ranked[: max(1, int(state.get("max_items") or 4))]
    return state


def _tool_analyze_items(case: dict[str, Any]):
    async def tool(state: dict[str, Any]) -> dict[str, Any]:
        risk_level = case.get("risk_level", "low")
        state["analyzed_news"] = [
            {
                "news": item,
                "analysis_result": {
                    "risk_result": {
                        "risk_level": risk_level,
                        "reason": f"{risk_level} risk eval fixture",
                    }
                },
                "status": "completed",
            }
            for item in state.get("selected_news") or []
        ]
        state["completed_results"] = [item["analysis_result"] for item in state["analyzed_news"]]
        state["overall_risk_level"] = risk_level
        return state

    return tool


async def _tool_risk_review(state: dict[str, Any]) -> dict[str, Any]:
    state["risk_review_checked"] = True
    if state.get("overall_risk_level") == "high":
        state["risk_review_notes"] = ["High risk route triggered for review."]
    else:
        state["risk_review_notes"] = []
    return state


def _tool_generate_report(case: dict[str, Any]):
    async def tool(state: dict[str, Any]) -> dict[str, Any]:
        report = "Market pulse research summary based on public news."
        if case.get("inject_unsafe_report"):
            report += " strong buy, guaranteed return, 建议买入, 必须买入, 稳赚, 保证收益"

        analyzed = state.get("analyzed_news") or []
        state["result"] = {
            "status": "completed",
            "query": state.get("query", ""),
            "report": report,
            "risk_level": state.get("overall_risk_level", "low"),
            "risk_review_notes": state.get("risk_review_notes", []),
            "analyzed_news": analyzed,
            "sources": [
                {
                    "source_url": item.get("news", {}).get("source_url"),
                    "source_metadata": item.get("news", {}).get("source_metadata"),
                }
                for item in analyzed
            ],
        }
        return state

    return tool


def _evaluate_case(case: dict[str, Any], trace, actions: list[str]) -> dict[str, Any]:
    expected_bits: list[str] = []
    actual_bits: list[str] = [f"status={trace.status}", f"actions={','.join(actions)}"]
    passed = True
    notes: list[str] = []

    if "expected_status" in case:
        expected_bits.append(f"status={case['expected_status']}")
        if trace.status != case["expected_status"]:
            passed = False
            notes.append(f"expected status {case['expected_status']}")

    if "expected_status_any_of" in case:
        expected_bits.append(f"status in {case['expected_status_any_of']}")
        if trace.status not in case["expected_status_any_of"]:
            passed = False
            notes.append("status was not accepted")

    if case.get("expected_actions"):
        expected = case["expected_actions"]
        expected_bits.append("actions=" + ",".join(expected))
        if actions[: len(expected)] != expected:
            passed = False
            notes.append("action order mismatch")

    result = trace.final_result or {}
    report = str(result.get("report") or "")

    if case.get("forbidden_phrases"):
        expected_bits.append("no forbidden phrases")
        remaining = [phrase for phrase in case["forbidden_phrases"] if phrase.lower() in report.lower()]
        actual_bits.append("remaining_forbidden=" + ",".join(remaining))
        if remaining:
            passed = False
            notes.append("forbidden phrases remained in final report")

    if case.get("risk_level") == "high":
        expected_bits.append("risk_review triggered")
        if "risk_review" not in actions or not result.get("risk_review_notes"):
            passed = False
            notes.append("high risk review was not recorded")

    if case.get("require_source_tracking"):
        expected_bits.append("source_url or source_metadata present")
        has_sources = _has_source_tracking(result)
        actual_bits.append(f"source_tracking={has_sources}")
        if not has_sources:
            passed = False
            notes.append("source metadata missing")

    if case.get("empty_news"):
        expected_bits.append("empty news reason in trace")
        summaries = " ".join(step.observation.summary for step in trace.steps)
        if "候选新闻不足" not in summaries and "External news source returned no items" not in summaries:
            passed = False
            notes.append("empty news reason missing")

    return {
        "expected": "; ".join(expected_bits) or "-",
        "actual": "; ".join(actual_bits),
        "passed": passed,
        "notes": "; ".join(notes) if notes else "OK",
    }


def _has_source_tracking(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("source_url") or value.get("source_metadata"):
            return True
        return any(_has_source_tracking(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_source_tracking(item) for item in value)
    return False


def _write_report(rows: list[dict[str, Any]]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Market Pulse Agent Eval Report",
        "",
        "| Case | Expected | Actual | Passed | Notes |",
        "| ---- | -------- | ------ | ------ | ----- |",
    ]
    for row in rows:
        lines.append(
            "| {case} | {expected} | {actual} | {passed} | {notes} |".format(
                case=_escape(row["case"]),
                expected=_escape(row["expected"]),
                actual=_escape(row["actual"]),
                passed="yes" if row["passed"] else "no",
                notes=_escape(row["notes"]),
            )
        )
    content = "\n".join(lines) + "\n"
    tmp_path = REPORT_PATH.with_suffix(".tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, REPORT_PATH)
    except PermissionError:
        if os.name != "nt":
            raise
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        target = str(REPORT_PATH).replace("'", "''")
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    f"$p='{target}'; "
                    f"$c='{encoded}'; "
                    "$text=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($c)); "
                    "Set-Content -LiteralPath $p -Value $text -Encoding UTF8"
                ),
            ],
            check=True,
        )


def _escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    asyncio.run(main())
