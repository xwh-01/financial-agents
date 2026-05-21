import asyncio

from market_pulse.analyzers.single_news_analysis import run_single_news_analysis
from market_pulse.schemas import AnalyzeRequest, DailyNewsAnalysis, WorkflowResult
from market_pulse.state import MarketPulseGraphState


async def analyze_items_node(
    state: MarketPulseGraphState,
) -> MarketPulseGraphState:
    """Run single-news analysis for each selected news item."""
    print("[langgraph-market] analyze_items")
    analyzed_news: list[DailyNewsAnalysis] = []
    completed_results: list[WorkflowResult] = []

    for item in state.get("selected_news", []):
        try:
            analyze_request = AnalyzeRequest(
                title=item.title,
                content=item.content,
                source=item.source or "news",
                published_at=item.published_at,
            )
            analysis_result = await asyncio.wait_for(
                run_single_news_analysis(analyze_request),
                timeout=90,
            )

            analyzed_news.append(
                DailyNewsAnalysis(
                    news=item,
                    analysis_result=analysis_result,
                    status=analysis_result.status,
                    error_message=analysis_result.error_message,
                )
            )

            if analysis_result.error_message is None:
                completed_results.append(analysis_result)

        except Exception as exc:
            error_message = (
                "analysis timed out after 90 seconds"
                if isinstance(exc, asyncio.TimeoutError)
                else str(exc)
            )
            analyzed_news.append(
                DailyNewsAnalysis(
                    news=item,
                    analysis_result=None,
                    status="failed",
                    error_message=error_message,
                )
            )

    return {
        "analyzed_news": analyzed_news,
        "completed_results": completed_results,
        "overall_risk_level": _overall_risk_level(completed_results),
    }


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
