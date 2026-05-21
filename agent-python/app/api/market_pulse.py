from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from market_pulse.schemas import (
    AnalyzeRequest,
    BatchAnalyzeNewsRequest,
    BatchAnalyzeNewsResponse,
    DailyBriefRequest,
    DailyBriefResponse,
    MarketPulseRequest,
    MarketPulseResponse,
    SearchNewsRequest,
    SearchNewsResponse,
)
from market_pulse.service import (
    run_batch_news_analysis,
    run_daily_brief,
    run_langgraph_market_pulse,
    run_market_pulse,
    run_single_news_analysis,
    search_news_items,
)


router = APIRouter()


class LangGraphMarketPulseRequest(BaseModel):
    query: str
    max_items: int = 5


@router.post("/agent/analyze")
async def analyze(request: AnalyzeRequest):
    result = await run_single_news_analysis(request)

    return JSONResponse(
        content=result.model_dump(),
        media_type="application/json; charset=utf-8",
    )


@router.post("/agent/search-news", response_model=SearchNewsResponse)
async def search_news_route(request: SearchNewsRequest):
    items = await search_news_items(request)
    return SearchNewsResponse(items=items)


@router.post("/agent/batch-analyze-news", response_model=BatchAnalyzeNewsResponse)
async def batch_analyze_news_route(request: BatchAnalyzeNewsRequest):
    return await run_batch_news_analysis(request)


@router.post("/agent/daily-brief", response_model=DailyBriefResponse)
async def daily_brief_route(request: DailyBriefRequest):
    return await run_daily_brief(request)


@router.post("/agent/market-pulse", response_model=MarketPulseResponse)
async def market_pulse_route(request: MarketPulseRequest):
    return await run_market_pulse(request)


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
