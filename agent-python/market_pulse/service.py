import asyncio

from clients.news_client import search_news
from clients.fin_news_rss import collect_fin_rss_news
from market_pulse.filters.news_filter import dedupe_news, filter_fresh_news
from market_pulse.analyzers.report_generator import (
    build_daily_trend_report,
    build_financial_recommendations,
    build_market_signal_report,
    build_market_signals,
    predict_ticker_trends,
)
from market_pulse.graph import run_langgraph_market_pulse as _run_langgraph_market_pulse
from market_pulse.rankers.news_ranker import filter_and_rank_news
from market_pulse.rankers.news_ranker import freshness_score, parse_news_time
from market_pulse.rankers.source_weight import get_source_weight
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
from market_pulse.workflows.single_news import (
    run_single_news_analysis as _run_single_news_analysis,
)


async def run_single_news_analysis(request: AnalyzeRequest) -> WorkflowResult:
    return await _run_single_news_analysis(request)


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

    candidate_news = await collect_fin_rss_news(
        limit=request.limit,
    )
    print("[market-pulse] candidate:", len(candidate_news))

    ranked_news = filter_and_rank_news(candidate_news)
    print("[market-pulse] ranked:", len(ranked_news))

    analysis_limit = min(request.max_items, 10)
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

    market_signals = build_market_signals(trends, analyzed_news)
    recommendations = build_financial_recommendations(trends)
    print("[market-pulse] market_signals:", len(market_signals))

    report = build_market_signal_report(market_signals)
    print("[market-pulse] done")

    return MarketPulseResponse(
        status="completed",
        total_news=len(news_items),
        candidate_news_count=len(candidate_news),
        filtered_news_count=len(ranked_news),
        analyzed_news_count=len(analyzed_news),
        analyzed_news=analyzed_news,
        trends=trends,
        market_signals=market_signals,
        recommendations=recommendations,
        report=report,
        error_message=None,
    )


async def run_fresh_opportunity_scan(
    limit: int = 180,
    max_items: int = 10,
) -> MarketPulseResponse:
    print("[opportunity-scan] start")
    candidate_news = await collect_fin_rss_news(limit=limit)
    deduped_news = dedupe_news(candidate_news)
    fresh_news = filter_fresh_news(deduped_news, max_age_hours=72)
    sorted_news = sorted(fresh_news, key=_fresh_opportunity_key, reverse=True)

    analysis_limit = max(3, min(max_items, 10))
    news_items = sorted_news[:analysis_limit]

    print(
        "[opportunity-scan] counts:",
        {
            "candidate": len(candidate_news),
            "deduped": len(deduped_news),
            "fresh": len(fresh_news),
            "selected": len(news_items),
        },
    )

    if not news_items:
        return MarketPulseResponse(
            status="completed",
            total_news=0,
            candidate_news_count=len(candidate_news),
            filtered_news_count=0,
            analyzed_news_count=0,
            analyzed_news=[],
            trends=[],
            recommendations=[],
            report=(
                "本次机会扫描没有获取到足够新的金融新闻。"
                "可以稍后重试，或检查 RSS/新闻源连接。本文仅为研究参考，不构成投资建议。"
            ),
            error_message=None,
        )

    analyzed_news: list[DailyNewsAnalysis] = []
    completed_results = []

    for idx, item in enumerate(news_items, start=1):
        item.relevance_score = _fresh_opportunity_key(item)[0]
        item.relevance_reasons = [
            "freshness_first",
            f"freshness_score={freshness_score(item):.2f}",
            f"source_weight={get_source_weight(item.source, item.url):.2f}",
        ]

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

            _attach_analysis_tickers(item, analysis_result)
            analyzed_news.append(
                DailyNewsAnalysis(
                    news=item,
                    analysis_result=analysis_result,
                    status=analysis_result.status,
                    error_message=analysis_result.error_message,
                )
            )

            if analysis_result.error_message is None and _has_stock_link(analysis_result):
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

    trends = predict_ticker_trends(completed_results)
    market_signals = build_market_signals(trends, analyzed_news)
    recommendations = build_financial_recommendations(trends)
    report = build_market_signal_report(market_signals)

    return MarketPulseResponse(
        status="completed",
        total_news=len(news_items),
        candidate_news_count=len(candidate_news),
        filtered_news_count=len(fresh_news),
        analyzed_news_count=len(analyzed_news),
        analyzed_news=analyzed_news,
        trends=trends,
        market_signals=market_signals,
        recommendations=recommendations,
        report=report,
        error_message=None,
    )


def _fresh_opportunity_key(item: NewsItem) -> tuple[float, float]:
    source = get_source_weight(item.source, item.url)
    fresh = freshness_score(item)
    content_bonus = 0.2 if len(item.content or "") >= 80 else 0.0
    published = parse_news_time(item.published_at)
    timestamp = published.timestamp() if published else 0.0
    return (fresh * 10 + source * 2 + content_bonus, timestamp)


def _attach_analysis_tickers(item: NewsItem, result: WorkflowResult) -> None:
    tickers: list[str] = []
    if result.entity_result:
        tickers.extend(result.entity_result.tickers)
    if result.ticker_links:
        tickers.extend(result.ticker_links.direct_tickers)
        tickers.extend(result.ticker_links.related_tickers)
        tickers.extend(result.ticker_links.etfs)
    item.matched_tickers = _dedupe_upper(tickers)
    if result.entity_result:
        item.matched_topics = _dedupe_upper(result.entity_result.topics)


def _has_stock_link(result: WorkflowResult) -> bool:
    if result.ticker_links and (
        result.ticker_links.direct_tickers
        or result.ticker_links.related_tickers
        or result.ticker_links.etfs
    ):
        return True
    return bool(result.entity_result and result.entity_result.tickers)


def _dedupe_upper(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item or "").strip().upper()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


async def run_langgraph_market_pulse(
    query: str,
    max_items: int = 8,
    tickers: list[str] | None = None,
    report_job_id: int | None = None,
    report_trace_id: int | None = None,
) -> dict:
    return await _run_langgraph_market_pulse(
        query=query,
        max_items=max_items,
        tickers=tickers,
        report_job_id=report_job_id,
        report_trace_id=report_trace_id,
    )


def list_reports(limit: int = 20) -> list[dict]:
    return _list_reports(limit=limit)


def get_report(report_id: int) -> dict | None:
    return _get_report(report_id)
