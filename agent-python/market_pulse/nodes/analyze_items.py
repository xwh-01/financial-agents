import asyncio

from app.config import settings
from market_pulse.analyzers.market_analyzer import get_market_failures, init_market_cache
from market_pulse.schemas import AnalyzeRequest, DailyNewsAnalysis, WorkflowResult
from market_pulse.state import MarketPulseGraphState
from market_pulse.workflows.single_news import run_single_news_analysis
from safety.compliance import sanitize_text


async def analyze_items_node(
    state: MarketPulseGraphState,
) -> MarketPulseGraphState:
    """
    Run single-news analysis concurrently for each selected news item.

    Steps per item:
      1. Resolve entities, events, and risk (via LLM in single_news workflow)
      2. Link entities to tickers (direct, related peers, ETFs)
      3. Fetch market data for linked tickers (Alpha Vantage, request-level cache)
      4. Generate per-item report and run compliance check

    Concurrency is controlled by market_pulse_analysis_concurrency, each item
    has its own timeout. Failed items are recorded with status="failed" but
    don't block the pipeline.

    After all items complete:
      - overall_risk_level is the max risk level across all results
      - market_data_error message is attached if Alpha Vantage failures occurred
    """
    print("[langgraph-market] analyze_items")
    # Initialize the request-level market data cache before concurrent analysis
    init_market_cache()
    selected_news = list(state.get("selected_news", []))
    concurrency = max(1, settings.market_pulse_analysis_concurrency)
    semaphore = asyncio.Semaphore(concurrency)
    analyzed_news = await asyncio.gather(
        *[_analyze_one_item(item, semaphore) for item in selected_news],
    )
    completed_results = [
        item.analysis_result
        for item in analyzed_news
        if item.analysis_result is not None and item.analysis_result.error_message is None
    ]

    return {
        "analyzed_news": analyzed_news,
        "completed_results": completed_results,
        "overall_risk_level": _overall_risk_level(completed_results),
        "error_message": _market_error_message() or None,
    }


async def _analyze_one_item(item, semaphore: asyncio.Semaphore) -> DailyNewsAnalysis:
    async with semaphore:
        timeout = settings.market_pulse_analysis_timeout_seconds
        try:
            analyze_request = AnalyzeRequest(
                title=item.title,
                content=item.content,
                source=item.source or "news",
                published_at=item.published_at,
            )
            analysis_result = await asyncio.wait_for(
                run_single_news_analysis(analyze_request),
                timeout=timeout,
            )
            if analysis_result.report:
                analysis_result.report, _ = sanitize_text(analysis_result.report)
            return DailyNewsAnalysis(
                news=item,
                analysis_result=analysis_result,
                status=analysis_result.status,
                error_message=analysis_result.error_message,
            )
        except Exception as exc:
            error_message = (
                f"analysis timed out after {timeout} seconds"
                if isinstance(exc, asyncio.TimeoutError)
                else str(exc)
            )
            return DailyNewsAnalysis(
                news=item,
                analysis_result=None,
                status="failed",
                error_message=error_message,
            )


def _overall_risk_level(results: list[WorkflowResult]) -> str:
    risk_rank = {"low": 0, "medium": 1, "high": 2}
    level = "low"

    for result in results:
        if not result.risk_result:
            continue
        candidate = result.risk_result.risk_level
        if risk_rank.get(candidate, 0) > risk_rank.get(level, 0):
            level = candidate

    return level


def _market_error_message() -> str:
    failures = get_market_failures()
    if not failures:
        return ""
    return (
        f"Market data unavailable for: {', '.join(failures)}. "
        "Check Alpha Vantage API key or rate limits."
    )
