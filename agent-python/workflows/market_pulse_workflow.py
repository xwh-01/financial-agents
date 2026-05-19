import asyncio

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

    candidate_news = await collect_latest_market_news(
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
                run_market_impact_workflow(analyze_request),
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
