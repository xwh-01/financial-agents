import asyncio

from app.config import settings
from market_pulse.schemas import AnalyzeRequest, DailyNewsAnalysis, WorkflowResult
from market_pulse.state import MarketPulseGraphState
from market_pulse.workflows.single_news import run_single_news_analysis


async def analyze_items_node(
    state: MarketPulseGraphState,
) -> MarketPulseGraphState:
    """Run single-news analysis for each selected news item."""
    print("[langgraph-market] analyze_items")
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
