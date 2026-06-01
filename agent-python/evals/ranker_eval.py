"""Ranker quality evaluation: Precision@5, Precision@10, important recall, irrelevant rate.

Outputs: terminal summary, JSON report, CSV summary table.

Usage:
  cd agent-python
  python evals/ranker_eval.py
"""
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from market_pulse.rankers.news_ranker import filter_and_rank_news
from market_pulse.schemas import NewsItem

DATASET_PATH = Path(__file__).resolve().parent / "ranker_eval_dataset.jsonl"
REPORT_JSON_PATH = Path(__file__).resolve().parent / "ranker_eval_report.json"
SUMMARY_CSV_PATH = Path(__file__).resolve().parent / "ranker_eval_summary.csv"

RELEVANT_LABELS = {"important", "related"}

WARN_PRECISION_AT_5 = 0.6
WARN_IRRELEVANT_RATE = 0.3
WARN_IMPORTANT_RECALL = 0.8


def load_dataset() -> list[dict]:
    samples: list[dict] = []
    with open(DATASET_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            sample = json.loads(line)
            _validate_sample(sample)
            samples.append(sample)
    if len(samples) < 30:
        print(f"[WARN] dataset has only {len(samples)} samples (< 30 recommended)")
    return samples


def _validate_sample(sample: dict) -> None:
    valid_labels = {"important", "related", "weakly_related", "irrelevant"}
    if sample.get("label") not in valid_labels:
        raise ValueError(
            f"Invalid label {sample.get('label')!r} in: {sample.get('title', '?')}"
        )
    required = ("query", "title", "label")
    for field in required:
        if not sample.get(field):
            raise ValueError(f"Missing field {field!r} in sample")


def group_by_query(samples: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for sample in samples:
        groups[sample["query"]].append(sample)
    return dict(groups)


def build_news_items(samples: list[dict]) -> list[NewsItem]:
    items: list[NewsItem] = []
    for idx, sample in enumerate(samples):
        items.append(
            NewsItem(
                index=idx,
                title=sample["title"],
                content=sample.get("description", ""),
                source=sample.get("source_name", ""),
                url=sample.get("url", ""),
                published_at=sample.get("published_at", ""),
            )
        )
    return items


def evaluate_query(query: str, samples: list[dict]) -> dict:
    items = build_news_items(samples)
    ranked = filter_and_rank_news(items, min_score=0, query=query)

    ranked_indices = [item.index for item in ranked if item.index is not None]
    labels = [s["label"] for s in samples]

    total = len(samples)
    top5_indices = ranked_indices[:5]
    top10_indices = ranked_indices[:10]

    def precision_at(k: int, idx_list: list[int]) -> float:
        if k == 0 or not idx_list:
            return 0.0
        relevant = sum(1 for i in idx_list[:k] if labels[i] in RELEVANT_LABELS)
        return relevant / min(k, len(idx_list[:k]))

    p5 = precision_at(5, top5_indices)
    p10 = precision_at(10, top10_indices)

    important_indices = [i for i, lbl in enumerate(labels) if lbl == "important"]
    important_in_top10 = len(set(important_indices) & set(top10_indices))
    important_recall_at_10 = (
        important_in_top10 / len(important_indices) if important_indices else 1.0
    )

    irrelevant_in_top10 = sum(1 for i in top10_indices if labels[i] == "irrelevant")
    irrelevant_rate_at_10 = (
        irrelevant_in_top10 / len(top10_indices) if top10_indices else 0.0
    )

    top_ranked = []
    for rank_idx, i in enumerate(top10_indices, start=1):
        item = ranked[ranked_indices.index(i)] if i in ranked_indices else None
        entry = {
            "rank": rank_idx,
            "label": labels[i],
            "title": samples[i]["title"],
        }
        if item:
            entry["relevance_score"] = round(item.relevance_score, 2)
            entry["source_weight"] = round(item.source_weight, 2)
            entry["freshness_score"] = round(item.freshness_score, 2)
            entry["negative_score"] = round(item.negative_score, 2)
            entry["relevance_reasons"] = list(item.relevance_reasons)
            entry["negative_reasons"] = list(item.negative_reasons)
        top_ranked.append(entry)

    fp_in_top5 = [
        {"label": labels[i], "title": samples[i]["title"]}
        for i in top5_indices if labels[i] not in RELEVANT_LABELS
    ]

    missed_imp = [
        samples[i]["title"] for i in important_indices if i not in top10_indices
    ]

    return {
        "query": query,
        "total_items": total,
        "precision_at_5": round(p5, 4),
        "precision_at_10": round(p10, 4),
        "important_recall_at_10": round(important_recall_at_10, 4),
        "irrelevant_rate_at_10": round(irrelevant_rate_at_10, 4),
        "top_ranked": top_ranked,
        "false_positives": fp_in_top5,
        "missed_important": missed_imp,
    }


def print_query_result(result: dict) -> None:
    print(f"\n=== Query: {result['query']} ===")
    print(f"total_items: {result['total_items']}")
    print(f"Precision@5: {result['precision_at_5']:.2f}")
    print(f"Precision@10: {result['precision_at_10']:.2f}")
    print(f"Important Recall@10: {result['important_recall_at_10']:.2f}")
    print(f"Irrelevant Rate@10: {result['irrelevant_rate_at_10']:.2f}")

    for entry in result["top_ranked"]:
        neg = ""
        if entry.get("negative_score", 0) != 0:
            neg = f" neg={entry['negative_score']}"
        print(
            f"  [{entry['label']}] "
            f"score={entry.get('relevance_score', '?')} "
            f"sw={entry.get('source_weight', '?')} "
            f"fsh={entry.get('freshness_score', '?')}{neg}  "
            f"{entry['title']}"
        )
        if entry.get("negative_reasons"):
            print(f"           neg_reasons: {', '.join(entry['negative_reasons'])}")

    _print_warnings(result)

    print("\nFalse positives (in top 5):")
    if result["false_positives"]:
        for fp in result["false_positives"]:
            print(f"  - [{fp['label']}] {fp['title']}")
    else:
        print("  none")

    print("\nMissed important:")
    if result["missed_important"]:
        for t in result["missed_important"]:
            print(f"  - {t}")
    else:
        print("  none")


def _print_warnings(result: dict) -> None:
    msgs: list[str] = []
    if result["precision_at_5"] < WARN_PRECISION_AT_5:
        msgs.append(
            f"Precision@5 ({result['precision_at_5']:.2f}) < {WARN_PRECISION_AT_5}"
        )
    if result["irrelevant_rate_at_10"] > WARN_IRRELEVANT_RATE:
        msgs.append(
            f"Irrelevant Rate@10 ({result['irrelevant_rate_at_10']:.2f}) > {WARN_IRRELEVANT_RATE}"
        )
    if result["important_recall_at_10"] < WARN_IMPORTANT_RECALL:
        msgs.append(
            f"Important Recall@10 ({result['important_recall_at_10']:.2f}) < {WARN_IMPORTANT_RECALL}"
        )
    for msg in msgs:
        print(f"  [WARN] {msg}")


def save_json_report(results: list[dict]) -> str:
    avg = _compute_overall(results)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(DATASET_PATH),
        "overall": avg,
        "warnings": {},
        "queries": results,
    }
    for r in results:
        warns: list[str] = []
        if r["precision_at_5"] < WARN_PRECISION_AT_5:
            warns.append(f"precision_at_5 < {WARN_PRECISION_AT_5}")
        if r["irrelevant_rate_at_10"] > WARN_IRRELEVANT_RATE:
            warns.append(f"irrelevant_rate_at_10 > {WARN_IRRELEVANT_RATE}")
        if r["important_recall_at_10"] < WARN_IMPORTANT_RECALL:
            warns.append(f"important_recall_at_10 < {WARN_IMPORTANT_RECALL}")
        if warns:
            report["warnings"][r["query"]] = warns

    with open(REPORT_JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    return str(REPORT_JSON_PATH)


def save_csv_summary(results: list[dict]) -> str:
    fields = [
        "query", "total_items", "precision_at_5", "precision_at_10",
        "important_recall_at_10", "irrelevant_rate_at_10",
        "false_positive_count", "missed_important_count",
    ]
    with open(SUMMARY_CSV_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            row = {k: r.get(k, 0) for k in fields}
            row["false_positive_count"] = len(r.get("false_positives", []))
            row["missed_important_count"] = len(r.get("missed_important", []))
            writer.writerow(row)
    return str(SUMMARY_CSV_PATH)


def _compute_overall(results: list[dict]) -> dict:
    if not results:
        return {}
    n = len(results)
    return {
        "queries_evaluated": n,
        "avg_precision_at_5": round(
            sum(r["precision_at_5"] for r in results) / n, 4
        ),
        "avg_precision_at_10": round(
            sum(r["precision_at_10"] for r in results) / n, 4
        ),
        "avg_important_recall_at_10": round(
            sum(r["important_recall_at_10"] for r in results) / n, 4
        ),
        "avg_irrelevant_rate_at_10": round(
            sum(r["irrelevant_rate_at_10"] for r in results) / n, 4
        ),
    }


def main() -> None:
    samples = load_dataset()
    print(f"Loaded {len(samples)} samples")

    groups = group_by_query(samples)
    results: list[dict] = []

    for query in sorted(groups.keys()):
        query_samples = groups[query]
        result = evaluate_query(query, query_samples)
        results.append(result)
        print_query_result(result)

    overall = _compute_overall(results)
    print("\n=== OVERALL AVERAGE ===")
    print(f"Queries evaluated: {overall['queries_evaluated']}")
    print(f"Avg Precision@5:  {overall['avg_precision_at_5']:.2f}")
    print(f"Avg Precision@10: {overall['avg_precision_at_10']:.2f}")
    print(f"Avg Important Recall@10: {overall['avg_important_recall_at_10']:.2f}")
    print(f"Avg Irrelevant Rate@10:  {overall['avg_irrelevant_rate_at_10']:.2f}")

    json_path = save_json_report(results)
    csv_path = save_csv_summary(results)
    print(f"\nJSON report: {json_path}")
    print(f"CSV summary: {csv_path}")
    print("Note: small-scale offline evaluation, not predictive of investment performance.")


if __name__ == "__main__":
    main()
