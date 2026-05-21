# Legacy compatibility module. New code should use market_pulse/...

from clients.news_client import search_news
from market_pulse.analyzers.single_news_analysis import run_single_news_analysis
from market_pulse.analyzers.trend_predictor import (
    build_daily_trend_report,
    predict_ticker_trends,
)
from market_pulse.schemas import (
    AnalyzeRequest,
    DailyBriefRequest,
    DailyBriefResponse,
    DailyNewsAnalysis,
)


async def run_daily_brief_workflow(request: DailyBriefRequest) -> DailyBriefResponse:
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
