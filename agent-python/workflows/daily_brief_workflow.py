from schemas.request import AnalyzeRequest
from schemas.trend import DailyBriefRequest, DailyBriefResponse, DailyNewsAnalysis
from tools.news_search import search_news
from workflows.market_impact_workflow import run_market_impact_workflow
from agents.trend_predictor import build_daily_trend_report, predict_ticker_trends


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
            analysis_result = await run_market_impact_workflow(analyze_request)
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
