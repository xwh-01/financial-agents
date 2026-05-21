import asyncio
import uuid

from market_pulse.analyzers.entity_resolver import resolve_entities
from market_pulse.analyzers.event_analyzer import analyze_event
from market_pulse.analyzers.market_analyzer import analyze_market
from market_pulse.analyzers.report_generator import check_compliance, generate_report
from market_pulse.analyzers.risk_checker import check_risk
from market_pulse.analyzers.ticker_linker import link_tickers
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
                _run_single_news_analysis(analyze_request),
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


async def _run_single_news_analysis(request: AnalyzeRequest) -> WorkflowResult:
    task_id = str(uuid.uuid4())

    try:
        entity_result = await resolve_entities(request)
        event_result = await analyze_event(request, entity_result)
        ticker_links = link_tickers(entity_result, event_result)
        market_metrics = await analyze_market(ticker_links, request.published_at)
        risk_result = check_risk(request, event_result, ticker_links)
        report_result = await generate_report(
            entity_result=entity_result,
            event_result=event_result,
            ticker_links=ticker_links,
            market_metrics=market_metrics,
            risk_result=risk_result,
        )
        compliance_result = check_compliance(report_result)

        return WorkflowResult(
            task_id=task_id,
            status="completed"
            if compliance_result.passed
            else "completed_with_compliance_warning",
            entity_result=entity_result,
            event_result=event_result,
            ticker_links=ticker_links,
            market_metrics=market_metrics,
            risk_result=risk_result,
            compliance_result=compliance_result,
            report=compliance_result.sanitized_report,
            error_message=None,
        )

    except Exception as exc:
        return WorkflowResult(
            task_id=task_id,
            status="failed",
            report="",
            error_message=str(exc),
        )
