from market_pulse.analyzers.single_news_analysis import (
    run_single_news_analysis as _run_single_news_analysis,
)
from market_pulse.graph import run_langgraph_market_pulse as _run_langgraph_market_pulse
from market_pulse.repository import get_report as _get_report
from market_pulse.repository import list_reports as _list_reports
from market_pulse.schemas import (
    AnalyzeRequest,
    DailyBriefRequest,
    DailyBriefResponse,
    MarketPulseRequest,
    MarketPulseResponse,
    WorkflowResult,
)
from workflows.daily_brief_workflow import run_daily_brief_workflow
from workflows.market_pulse_workflow import run_market_pulse_workflow


async def run_single_news_analysis(request: AnalyzeRequest) -> WorkflowResult:
    return await _run_single_news_analysis(request)


async def run_daily_brief(request: DailyBriefRequest) -> DailyBriefResponse:
    return await run_daily_brief_workflow(request)


async def run_market_pulse(request: MarketPulseRequest) -> MarketPulseResponse:
    return await run_market_pulse_workflow(request)


async def run_langgraph_market_pulse(query: str, max_items: int = 5) -> dict:
    return await _run_langgraph_market_pulse(query=query, max_items=max_items)


def list_reports(limit: int = 20) -> list[dict]:
    return _list_reports(limit=limit)


def get_report(report_id: int) -> dict | None:
    return _get_report(report_id)
