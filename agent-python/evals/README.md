# Ranker Quality Evaluation

Offline evaluation of the Market Pulse news ranker using a labeled dataset.

## Dataset

`ranker_eval_dataset.jsonl` — one JSON sample per line, 56+ labeled news items across 5 queries.

### Label Definitions

| label | meaning |
|-------|---------|
| `important` | Highly relevant to query, directly impacts the market |
| `related` | Relevant to query, worth attention |
| `weakly_related` | Tangentially related, not counted toward precision |
| `irrelevant` | Not relevant, should be filtered by the ranker |

### Queries Covered

- NVIDIA AI chips (12 samples)
- Fed interest rate (11 samples)
- gold market (11 samples)
- Apple earnings (11 samples)
- oil prices (11 samples)

Each query includes boundary cases: ticker hits with weak semantics, authority mismatch, keyword ambiguity (e.g. "Apple" fruit vs stock, "gold" jewelry vs price), and strong/weak negatives.

## Evaluation Metrics

- **Precision@5 / @10**: proportion of top 5/10 with label `important` or `related`
- **Important Recall@10**: how many `important` samples appear in top 10
- **Irrelevant Rate@10**: proportion of top 10 with label `irrelevant`
- **False Positives**: non-relevant items entering top 5
- **Missed Important**: `important` items absent from top 10

## Running

```powershell
cd agent-python
python evals/ranker_eval.py
```

## Outputs

| file | format | content |
|------|--------|---------|
| terminal | text | per-query metrics, top ranked, warnings |
| `evals/ranker_eval_report.json` | JSON | structured report with all scores, reasons |
| `evals/ranker_eval_summary.csv` | CSV | one row per query, suitable for spreadsheets |

## Threshold Warnings

The script prints warnings (but does **not** exit) when:
- `precision_at_5 < 0.6`
- `irrelevant_rate_at_10 > 0.3`
- `important_recall_at_10 < 0.8`

Warnings are also written to the JSON report.

## Notes

- This is a small-scale offline relevance evaluation (~56 samples), not a market prediction benchmark.
- False positives and missed items can be used to iteratively improve ranker rules.
- Do not introduce ML models or vector databases for this eval.
- Labeled data is manually curated; update it when ranker behavior changes.
