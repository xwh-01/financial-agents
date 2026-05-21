import uuid

from market_pulse.analyzers.compliance_checker import check_compliance
from market_pulse.analyzers.entity_resolver import resolve_entities
from market_pulse.analyzers.event_analyzer import analyze_event
from market_pulse.analyzers.market_analyzer import analyze_market
from market_pulse.analyzers.report_generator import generate_report
from market_pulse.analyzers.risk_checker import check_risk
from market_pulse.analyzers.ticker_linker import link_tickers
from market_pulse.schemas import AnalyzeRequest, WorkflowResult


async def run_single_news_analysis(request: AnalyzeRequest) -> WorkflowResult:
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
