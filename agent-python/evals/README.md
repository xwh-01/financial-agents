# Ranker Quality Evaluation

Offline evaluation of the Market Pulse news ranker Layer 1 (coarse_filter) using labeled mock data.

## Dataset

`ranker_eval_dataset.jsonl` — 119 labeled samples across 9 query groups (10 are filtered by hard-filter, leaving 109 effective samples).

## Label Definitions

| label | meaning |
|-------|---------|
| `important` | Highly relevant to the query and should appear near the top |
| `related` | Relevant to the query and worth attention |
| `weakly_related` | Tangentially related, not counted toward precision |
| `irrelevant` | Not relevant and should be filtered or ranked low |

## Queries Covered

- `NVDA earnings AI chips` (free text, Chinese title)
- `Fed rate policy inflation` (free text, Chinese title)
- `gold precious metals safe haven` (free text, Chinese title)
- `tickers: NVDA, AMD\ntopics: data center, AI chips` (structured multi-intent)
- `oil crude energy OPEC supply` (free text)
- `Tesla robotaxi margins deliveries` (free text, Chinese title)
- `banks financial credit risk earnings` (free text, Chinese title)
- `semiconductor chip export China regulation` (free text)
- `macro: Fed rates, CPI\ncommodity: oil, gold` (structured multi-intent)

Each query includes: Chinese titles, real-world style long headlines with ticker symbols, edge cases (empty titles, short content, missing URLs), diverse distractor types (crypto spam, Telegram scams, SEO promotions, gaming, food, fashion, pets, sports).

## Evaluation Metrics

- **Precision@5 / @10**: proportion of top 5/10 with label `important` or `related`
- **Important Recall@10**: how many `important` samples appear in top 10
- **Irrelevant Rate@10**: proportion of top 10 with label `irrelevant`

Note: this evaluates Layer 1 (coarse_filter) only. Layers 2 (embedding) and 3 (LLM re-rank) require API integration and are not tested offline.

## Running

```powershell
cd agent-python
python evals/ranker_eval.py
```

## Outputs

| file | format | content |
|------|--------|---------|
| terminal | text | per-query metrics, top ranked, warnings |
| `evals/ranker_eval_report.json` | JSON | structured report with all scores |
| `evals/ranker_eval_summary.csv` | CSV | one row per query |
