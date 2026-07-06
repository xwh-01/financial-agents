"""Verify report guard: unsafe text detection and disclaimer appending.

Usage:
  python scripts/check_report_guard.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reports.guard import append_disclaimer, apply_report_guard, scan_unsafe_text


def test_scan_safe() -> None:
    print("=== safe text ===")
    text = "NVIDIA AI芯片需求可能影响后续市场关注度，建议投资者结合自身判断。"
    result = scan_unsafe_text(text)
    print(f"  is_unsafe: {result['is_unsafe']}")
    print(f"  risk_level: {result['risk_level']}")
    print(f"  matched_terms: {result['matched_terms']}")


def test_scan_risky() -> None:
    print("\n=== risky text ===")
    text = "建议买入 NVIDIA AI 芯片股票"
    result = scan_unsafe_text(text)
    print(f"  is_unsafe: {result['is_unsafe']}")
    print(f"  risk_level: {result['risk_level']}")
    print(f"  matched_terms: {result['matched_terms']}")


def test_scan_unsafe() -> None:
    print("\n=== unsafe text ===")
    text = "稳赚不赔！强烈推荐买入 NVIDIA！无风险、保证收益"
    result = scan_unsafe_text(text)
    print(f"  is_unsafe: {result['is_unsafe']}")
    print(f"  risk_level: {result['risk_level']}")
    print(f"  matched_terms: {result['matched_terms']}")


def test_apply_guard() -> None:
    print("\n=== apply_report_guard ===")
    report = {
        "summary": "NVIDIA 股票稳赚不赔，强烈推荐买入。",
        "report": "AI芯片市场持续增长，强烈推荐买入 NVIDIA 并满仓持有。",
        "analyzed_news": [
            {
                "news": {"title": "NVIDIA前景看好"},
                "analysis_result": {"report": "建议买入 NVIDIA"},
            }
        ],
    }
    guarded = apply_report_guard(report)
    print(f"  compliance_status: {guarded['compliance_status']}")
    print(f"  warnings: {guarded['compliance_warnings']}")
    print(f"  disclaimer present: {'disclaimer' in guarded}")


def test_disclaimer() -> None:
    print("\n=== append_disclaimer ===")
    text = "Market analysis: AI chip demand rising."
    result = append_disclaimer(text)
    has_disclaimer = "不构成任何投资建议" in result
    print(f"  original: {text}")
    print(f"  has_disclaimer: {has_disclaimer}")


def test_safe_report() -> None:
    print("\n=== safe report (no unsafe terms) ===")
    report = {
        "summary": "值得关注，后续观察。市场可能受到影响。",
        "analyzed_news": [],
    }
    guarded = apply_report_guard(report)
    print(f"  compliance_status: {guarded['compliance_status']}")
    print(f"  warnings: {guarded['compliance_warnings']}")


if __name__ == "__main__":
    test_scan_safe()
    test_scan_risky()
    test_scan_unsafe()
    test_apply_guard()
    test_disclaimer()
    test_safe_report()
    print("\n=== ALL GUARD CHECKS COMPLETED ===")
