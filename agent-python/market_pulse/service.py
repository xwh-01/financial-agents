import asyncio
import uuid

from clients.news_client import search_news
from clients.rss_client import collect_company_market_news
from market_pulse.analyzers.entity_resolver import resolve_entities
from market_pulse.analyzers.event_analyzer import analyze_event
from market_pulse.analyzers.market_analyzer import analyze_market
from market_pulse.analyzers.report_generator import (
    build_daily_trend_report,
    build_financial_recommendations,
    build_market_pulse_report,
    check_compliance,
    generate_report,
    predict_ticker_trends,
)
from market_pulse.analyzers.risk_checker import check_risk
from market_pulse.analyzers.ticker_linker import link_tickers
from market_pulse.graph import run_langgraph_market_pulse as _run_langgraph_market_pulse
from market_pulse.rankers.news_ranker import filter_and_rank_news
from market_pulse.repository import get_report as _get_report
from market_pulse.repository import list_reports as _list_reports
from market_pulse.schemas import (
    AnalyzeRequest,
    BatchAnalyzeNewsRequest,
    BatchAnalyzeNewsResponse,
    DailyBriefRequest,
    DailyBriefResponse,
    DailyNewsAnalysis,
    MarketPulseRequest,
    MarketPulseResponse,
    NewsAnalysisItem,
    NewsItem,
    SearchNewsRequest,
    WorkflowResult,
)


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


async def search_news_items(request: SearchNewsRequest) -> list[NewsItem]:
    return await search_news(
        query=request.query,
        limit=request.limit,
        language=request.language,
        translate_to_zh=request.translate_to_zh,
    )


async def run_batch_news_analysis(
    request: BatchAnalyzeNewsRequest,
) -> BatchAnalyzeNewsResponse:
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

            analysis_result = await run_single_news_analysis(analyze_request)

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


async def run_daily_brief(request: DailyBriefRequest) -> DailyBriefResponse:
    news_items = []
    seen_urls = set()
    seen_titles = set()

    for query in request.queries:
        items = await search_news(
            query=query,
            limit=request.limit_per_query,
            language=request.language,
            translate_to_zh=request.translate_to_zh,
        )

        for item in items:
            url_key = item.url.strip().lower()
            title_key = item.title.strip().lower()
            if url_key and url_key in seen_urls:
                continue
            if title_key and title_key in seen_titles:
                continue

            if url_key:
                seen_urls.add(url_key)
            if title_key:
                seen_titles.add(title_key)

            news_items.append(item)
            if len(news_items) >= request.max_items:
                break

        if len(news_items) >= request.max_items:
            break

    analyzed_news: list[DailyNewsAnalysis] = []
    completed_results = []

    for item in news_items:
        try:
            analyze_request = AnalyzeRequest(
                title=item.title,
                content=item.content,
                source=item.source or "news",
                published_at=item.published_at,
            )
            analysis_result = await run_single_news_analysis(analyze_request)
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
            analyzed_news.append(
                DailyNewsAnalysis(
                    news=item,
                    analysis_result=None,
                    status="failed",
                    error_message=str(exc),
                )
            )

    trends = predict_ticker_trends(completed_results)
    report = build_daily_trend_report(trends)

    return DailyBriefResponse(
        status="completed",
        queries=request.queries,
        total_news=len(news_items),
        analyzed_news=analyzed_news,
        trends=trends,
        report=report,
        error_message=None,
    )


async def run_market_pulse(request: MarketPulseRequest) -> MarketPulseResponse:
    print("[market-pulse] start")
    print(
        "[market-pulse] request:",
        {
            "limit": request.limit,
            "max_items": request.max_items,
            "language": request.language,
            "translate_to_zh": request.translate_to_zh,
        },
    )

    candidate_news = await collect_company_market_news(
        limit=request.limit,
        language=request.language,
        translate_to_zh=False,
    )
    print("[market-pulse] candidate:", len(candidate_news))

    ranked_news = filter_and_rank_news(candidate_news)
    print("[market-pulse] ranked:", len(ranked_news))

    analysis_limit = min(request.max_items, 5)
    news_items = ranked_news[:analysis_limit]

    print("[market-pulse] max_items requested:", request.max_items)
    print("[market-pulse] analysis_limit:", analysis_limit)
    print("[market-pulse] selected:", len(news_items))

    if not news_items:
        return MarketPulseResponse(
            status="completed",
            total_news=0,
            candidate_news_count=len(candidate_news),
            filtered_news_count=len(ranked_news),
            analyzed_news_count=0,
            analyzed_news=[],
            trends=[],
            recommendations=[],
            report=(
                "本次扫描没有筛选出足够相关的财经新闻。"
                "可能原因是新闻 API 返回内容相关性较低、候选新闻数量太少，"
                "或者当前相关性过滤阈值偏高。本文仅为研究参考，不构成投资建议。"
            ),
            error_message=None,
        )

    analyzed_news: list[DailyNewsAnalysis] = []
    completed_results = []

    for idx, item in enumerate(news_items, start=1):
        print(f"[market-pulse] analyzing {idx}/{len(news_items)}:", item.title[:80])
        print(
            f"[market-pulse] news score {idx}:",
            {
                "relevance_score": getattr(item, "relevance_score", 0),
                "matched_tickers": getattr(item, "matched_tickers", []),
                "matched_topics": getattr(item, "matched_topics", []),
            },
        )

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

            print(f"[market-pulse] analyzed {idx}/{len(news_items)}")

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
            print(f"[market-pulse] analyze failed {idx}/{len(news_items)}:", repr(exc))
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

    print("[market-pulse] completed_results:", len(completed_results))

    trends = predict_ticker_trends(completed_results)
    print("[market-pulse] trends:", len(trends))

    recommendations = build_financial_recommendations(trends)
    print("[market-pulse] recommendations:", len(recommendations))

    report = build_market_pulse_report(trends, recommendations)
    print("[market-pulse] done")

    return MarketPulseResponse(
        status="completed",
        total_news=len(news_items),
        candidate_news_count=len(candidate_news),
        filtered_news_count=len(ranked_news),
        analyzed_news_count=len(analyzed_news),
        analyzed_news=analyzed_news,
        trends=trends,
        recommendations=recommendations,
        report=report,
        error_message=None,
    )


async def run_langgraph_market_pulse(query: str, max_items: int = 5) -> dict:
    return await _run_langgraph_market_pulse(query=query, max_items=max_items)


def list_reports(limit: int = 20) -> list[dict]:
    return _list_reports(limit=limit)


def get_report(report_id: int) -> dict | None:
    return _get_report(report_id)
