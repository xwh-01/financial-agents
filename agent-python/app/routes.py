from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from schemas.request import AnalyzeRequest
from schemas.news import (
    SearchNewsRequest,
    SearchNewsResponse,
    BatchAnalyzeNewsRequest,
    BatchAnalyzeNewsResponse,
    NewsAnalysisItem,
)
from schemas.trend import (
    DailyBriefRequest,
    DailyBriefResponse,
    MarketPulseRequest,
    MarketPulseResponse,
)
from workflows.market_impact_workflow import run_market_impact_workflow
from workflows.daily_brief_workflow import run_daily_brief_workflow
from workflows.market_pulse_workflow import run_market_pulse_workflow
from workflows.langgraph_market_workflow import run_langgraph_market_pulse
from storage.report_store import get_report, list_reports
from tools.news_search import search_news


router = APIRouter()


class LangGraphMarketPulseRequest(BaseModel):
    query: str
    max_items: int = 5


@router.get("/healthz")
def healthz():
    return {"status": "ok"}


@router.post("/agent/analyze")
async def analyze(request: AnalyzeRequest):
    result = await run_market_impact_workflow(request)

    return JSONResponse(
        content=result.model_dump(),
        media_type="application/json; charset=utf-8",
    )


@router.post("/agent/search-news", response_model=SearchNewsResponse)
async def search_news_route(request: SearchNewsRequest):
    items = await search_news(
        query=request.query,
        limit=request.limit,
        language=request.language,
        translate_to_zh=request.translate_to_zh,
    )
    return SearchNewsResponse(items=items)


@router.post("/agent/batch-analyze-news", response_model=BatchAnalyzeNewsResponse)
async def batch_analyze_news_route(request: BatchAnalyzeNewsRequest):
    items = await search_news(
        query=request.query,
        limit=request.limit,
        language=request.language,
        translate_to_zh=request.translate_to_zh,
    )

    results: list[NewsAnalysisItem] = []

    for item in items:
        try:
            analyze_request = AnalyzeRequest(
                title=item.title,
                content=item.content,
                source=item.source or "news",
                published_at=item.published_at,
            )

            analysis_result = await run_market_impact_workflow(analyze_request)

            results.append(
                NewsAnalysisItem(
                    news=item,
                    analysis_result=analysis_result,
                    status="completed",
                    error_message=None,
                )
            )

        except Exception as exc:
            results.append(
                NewsAnalysisItem(
                    news=item,
                    analysis_result=None,
                    status="failed",
                    error_message=str(exc),
                )
            )

    return BatchAnalyzeNewsResponse(
        query=request.query,
        total=len(results),
        results=results,
    )


@router.post("/agent/daily-brief", response_model=DailyBriefResponse)
async def daily_brief_route(request: DailyBriefRequest):
    return await run_daily_brief_workflow(request)


@router.post("/agent/market-pulse", response_model=MarketPulseResponse)
async def market_pulse_route(request: MarketPulseRequest):
    return await run_market_pulse_workflow(request)


# Current recommended Market Pulse main entry.
# This route delegates the request to the LangGraph workflow and returns
# the persisted report payload with report_id.
@router.post("/api/agent/market-pulse/langgraph")
async def langgraph_market_pulse_route(request: LangGraphMarketPulseRequest):
    result = await run_langgraph_market_pulse(
        query=request.query,
        max_items=request.max_items,
    )

    return JSONResponse(
        content=result,
        media_type="application/json; charset=utf-8",
    )


@router.get("/api/reports")
async def reports_route():
    return list_reports(limit=20)


@router.get("/api/reports/{report_id}")
async def report_detail_route(report_id: int):
    report = get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    return report
