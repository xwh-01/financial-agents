from schemas.request import AnalyzeRequest
from schemas.trend import MarketPulseRequest, MarketPulseResponse, DailyNewsAnalysis
from tools.news_collector import collect_latest_market_news
from tools.news_ranker import filter_and_rank_news
from workflows.market_impact_workflow import run_market_impact_workflow
from agents.trend_predictor import (
    build_financial_recommendations,
    build_market_pulse_report,
    predict_ticker_trends,
)


async def run_market_pulse_workflow(request: MarketPulseRequest) -> MarketPulseResponse:
    candidate_news = await collect_latest_market_news(
        limit=request.limit,
        language=request.language,
        translate_to_zh=request.translate_to_zh,
)

    ranked_news = filter_and_rank_news(candidate_news)
    news_items = ranked_news[: request.max_items]

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
    recommendations = build_financial_recommendations(trends)
    report = build_market_pulse_report(trends, recommendations)

    return MarketPulseResponse(
        status="completed",
        total_news=len(news_items),
        analyzed_news=analyzed_news,
        trends=trends,
        recommendations=recommendations,
        report=report,
        error_message=None,
    )
