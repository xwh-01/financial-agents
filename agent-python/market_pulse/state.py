from typing import Any, TypedDict

from market_pulse.schemas import DailyNewsAnalysis, NewsItem, WorkflowResult


class MarketPulseGraphState(TypedDict, total=False):
    """
    Shared state dictionary flowing through the LangGraph Market Pulse workflow.

    Nodes read from and write to this state in sequence, with each node enriching
    the state for downstream consumers. Fields are optional (total=False) so that
    the initial state only needs to provide the few required inputs.

    Data flow by node:
      collect_news   -> candidate_news, collect_stats
      rank_news      -> ranked_news, selected_news
      analyze_items  -> analyzed_news, completed_results, overall_risk_level
      risk_route     -> (reads overall_risk_level for conditional routing)
      risk_review    -> risk_review_notes
      generate_report -> result
    """

    # ---- Inputs (provided at invocation) ----
    query: str                 # User query / watchlist intent string
    max_items: int             # Max number of news items to analyze (typically 8)
    tickers: list[str]         # Explicit tickers to focus on (optional)

    # ---- Intermediate data (populated by nodes) ----
    candidate_news: list[NewsItem]          # Raw news pool from external sources
    collect_stats: dict[str, Any]           # Per-source collection metrics (counts, errors)
    ranked_news: list[NewsItem]             # Ranked + filtered candidates
    selected_news: list[NewsItem]           # Final selected items for analysis (top-K)
    analyzed_news: list[DailyNewsAnalysis]  # Per-item analysis results (with status/error)
    completed_results: list[WorkflowResult] # Successfully completed analysis results only
    overall_risk_level: str                 # Aggregated risk level ("low" / "high")
    risk_review_notes: list[str]            # Human-readable risk observations

    # ---- Observability / tracing ----
    trace_id: str                           # Unique ID for this run's trace file
    trace_events: list[dict[str, Any]]      # Accumulated trace events across nodes
    report_job_id: int                      # Optional report job ID for scheduled runs
    report_trace_id: int                    # Optional report trace ID for scheduled runs

    # ---- Output ----
    result: dict[str, Any]                  # Final assembled report payload
    error_message: str | None               # Non-empty if the pipeline errored out
