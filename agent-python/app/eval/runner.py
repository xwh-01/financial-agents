from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from app.eval.metrics import calculate_metrics
from app.schemas import EvalCase, EvalResult, NewsItem
from app.services.ranking_service import rank_news


EVAL_DIR = Path(__file__).resolve().parent
CASES_PATH = EVAL_DIR / "cases.jsonl"
RESULTS_DIR = EVAL_DIR / "results"
LATEST_PATH = RESULTS_DIR / "latest.json"


def load_cases(path: Path = CASES_PATH) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            cases.append(EvalCase.model_validate_json(line))
    return cases


def run_eval() -> EvalResult:
    cases = load_cases()
    items = [
        NewsItem(
            title=case.title,
            summary=case.summary,
            source=case.source,
            url=case.url,
            published_at=case.published_at,
            symbol=case.symbol or None,
        )
        for case in cases
    ]
    started = time.perf_counter()
    ranked = rank_news(items, query="market impact earnings inflation AI oil risk")
    average_latency_ms = ((time.perf_counter() - started) * 1000) / max(len(cases), 1)
    metrics = calculate_metrics(ranked, cases, average_latency_ms=average_latency_ms)
    return EvalResult(
        generated_at=datetime.now(timezone.utc).isoformat(),
        metrics=metrics,
        ranked_titles=[item.title for item in ranked],
        average_latency_ms=metrics["average_latency_ms"],
        cases=[
            {
                "title": item.title,
                "symbol": item.symbol,
                "impact_score": item.impact_score,
                "expected_important": next(
                    case.expected_important for case in cases if case.title == item.title
                ),
                "reason": item.reason,
            }
            for item in ranked
        ],
    )


def print_table(result: EvalResult) -> None:
    print("\nFinancial Agents Ranking Eval")
    print("+----------------------+----------+")
    print("| Metric               | Value    |")
    print("+----------------------+----------+")
    for key, value in result.metrics.items():
        print(f"| {key:<20} | {value:<8} |")
    print("+----------------------+----------+")
    print(f"Saved: {LATEST_PATH}")


def save_result(result: EvalResult) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_PATH.write_text(
        json.dumps(result.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    result = run_eval()
    save_result(result)
    print_table(result)


if __name__ == "__main__":
    main()

