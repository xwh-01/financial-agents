# Legacy compatibility module. New code should use market_pulse/...

from market_pulse.analyzers.single_news_analysis import run_single_news_analysis
from market_pulse.schemas import AnalyzeRequest, WorkflowResult


async def run_market_impact_workflow(request: AnalyzeRequest) -> WorkflowResult:
    return await run_single_news_analysis(request)
