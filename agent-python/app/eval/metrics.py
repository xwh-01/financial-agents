from __future__ import annotations

from app.schemas import EvalCase, RankedNewsItem


def calculate_metrics(
    ranked_items: list[RankedNewsItem],
    cases: list[EvalCase],
    average_latency_ms: float,
) -> dict[str, float]:
    expected = {case.title: case.expected_important for case in cases}
    return {
        "Precision@5": _precision_at(ranked_items, expected, 5),
        "Precision@10": _precision_at(ranked_items, expected, 10),
        "ImportantRecall@10": _important_recall_at(ranked_items, expected, 10),
        "IrrelevantRate@10": _irrelevant_rate_at(ranked_items, expected, 10),
        "average_latency_ms": round(average_latency_ms, 3),
    }


def _precision_at(
    ranked_items: list[RankedNewsItem],
    expected: dict[str, bool],
    k: int,
) -> float:
    top = ranked_items[:k]
    if not top:
        return 0.0
    hits = sum(1 for item in top if expected.get(item.title) is True)
    return round(hits / len(top), 3)


def _important_recall_at(
    ranked_items: list[RankedNewsItem],
    expected: dict[str, bool],
    k: int,
) -> float:
    important_total = sum(1 for value in expected.values() if value)
    if important_total == 0:
        return 0.0
    top_titles = {item.title for item in ranked_items[:k]}
    hits = sum(1 for title, value in expected.items() if value and title in top_titles)
    return round(hits / important_total, 3)


def _irrelevant_rate_at(
    ranked_items: list[RankedNewsItem],
    expected: dict[str, bool],
    k: int,
) -> float:
    top = ranked_items[:k]
    if not top:
        return 0.0
    misses = sum(1 for item in top if expected.get(item.title) is False)
    return round(misses / len(top), 3)

