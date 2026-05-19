from collections import defaultdict

from schemas.trend import TickerTrend
from schemas.trend import FinancialRecommendation
from schemas.workflow import WorkflowResult


SENTIMENT_SCORE = {
    "positive": 1.0,
    "neutral": 0.0,
    "negative": -1.0,
}

RISK_PENALTY = {
    "low": 0.0,
    "medium": 0.15,
    "high": 0.3,
}


def predict_ticker_trends(results: list[WorkflowResult]) -> list[TickerTrend]:
    buckets: dict[str, list[WorkflowResult]] = defaultdict(list)

    for result in results:
        if result.status not in {"completed", "completed_with_compliance_warning"}:
            continue
        if not result.ticker_links:
            continue

        tickers = _dedupe(
            result.ticker_links.direct_tickers
            + result.ticker_links.related_tickers
            + result.ticker_links.etfs
        )
        for ticker in tickers:
            buckets[ticker].append(result)

    trends = [_build_ticker_trend(ticker, items) for ticker, items in buckets.items()]
    return sorted(
        trends,
        key=lambda item: (item.impact_score * item.confidence, item.news_count),
        reverse=True,
    )


def _build_ticker_trend(ticker: str, results: list[WorkflowResult]) -> TickerTrend:
    weighted_scores: list[float] = []
    confidence_values: list[float] = []
    impact_values: list[float] = []
    risk_flags: list[str] = []
    reasons: list[str] = []
    source_titles: list[str] = []
    max_risk_level = "low"

    for result in results:
        event = result.event_result
        risk = result.risk_result
        links = result.ticker_links

        if not event or not links:
            continue

        sentiment = SENTIMENT_SCORE.get(event.sentiment, 0.0)
        impact = _clamp(event.impact_score)
        confidence = _clamp((event.confidence + links.confidence) / 2)
        risk_level = risk.risk_level if risk else "low"
        penalty = RISK_PENALTY.get(risk_level, 0.0)

        score = sentiment * impact * confidence
        if score > 0:
            score = max(0.0, score - penalty)
        elif score < 0:
            score = min(0.0, score + penalty)

        weighted_scores.append(score)
        confidence_values.append(confidence)
        impact_values.append(impact)

        if event.summary:
            reasons.append(event.summary)
        if risk:
            risk_flags.extend(risk.risk_flags)
            max_risk_level = _max_risk(max_risk_level, risk.risk_level)

        if result.report:
            title = _extract_report_title(result.report)
            if title:
                source_titles.append(title)

    average_score = (
        sum(weighted_scores) / len(weighted_scores) if weighted_scores else 0.0
    )
    average_confidence = (
        sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
    )
    average_impact = sum(impact_values) / len(impact_values) if impact_values else 0.0

    return TickerTrend(
        ticker=ticker,
        direction=_direction_from_score(average_score),
        confidence=round(_clamp(average_confidence), 2),
        impact_score=round(_clamp(average_impact), 2),
        risk_level=max_risk_level,
        news_count=len(results),
        reasons=_dedupe(reasons)[:5],
        risk_flags=_dedupe(risk_flags),
        source_titles=_dedupe(source_titles)[:5],
    )


def build_daily_trend_report(trends: list[TickerTrend]) -> str:
    if not trends:
        return (
            "今日未识别到足够明确的股票趋势信号。\n\n"
            "免责声明：本报告仅用于舆情事件分析与学习展示，不构成投资建议。"
        )

    lines = [
        "每日新闻股票趋势简报",
        "",
        "说明：以下结论是基于新闻舆情、事件强度、关联股票和风险因子的短期倾向分析，不代表确定性预测。",
        "",
    ]

    for idx, trend in enumerate(trends, start=1):
        lines.extend(
            [
                f"{idx}. {trend.ticker}",
                f"趋势倾向：{trend.direction}",
                f"置信度：{trend.confidence:.2f}",
                f"影响强度：{trend.impact_score:.2f}",
                f"风险等级：{trend.risk_level}",
                f"相关新闻数量：{trend.news_count}",
            ]
        )

        if trend.reasons:
            lines.append("主要原因：")
            lines.extend([f"- {reason}" for reason in trend.reasons])

        if trend.risk_flags:
            lines.append(f"风险标记：{', '.join(trend.risk_flags)}")

        lines.append("")

    lines.append("免责声明：本报告仅用于舆情事件分析与学习展示，不构成投资建议。")
    return "\n".join(lines)


def build_financial_recommendations(
    trends: list[TickerTrend],
) -> list[FinancialRecommendation]:
    recommendations: list[FinancialRecommendation] = []

    for trend in trends:
        if trend.risk_level == "high":
            recommendation_type = "风险预警"
            time_window = "1-3 个交易日"
        elif trend.direction == "偏正面" and trend.confidence >= 0.55:
            recommendation_type = "推荐关注"
            time_window = "1-5 个交易日"
        elif trend.direction == "偏负面":
            recommendation_type = "谨慎观察"
            time_window = "1-5 个交易日"
        else:
            recommendation_type = "加入观察列表"
            time_window = "3-10 个交易日"

        rationale = _build_recommendation_rationale(trend)
        recommendations.append(
            FinancialRecommendation(
                ticker=trend.ticker,
                recommendation_type=recommendation_type,
                direction=trend.direction,
                confidence=trend.confidence,
                risk_level=trend.risk_level,
                time_window=time_window,
                rationale=rationale,
                watch_points=trend.reasons[:3],
                risk_flags=trend.risk_flags,
            )
        )

    return recommendations


def build_market_pulse_report(
    trends: list[TickerTrend],
    recommendations: list[FinancialRecommendation],
) -> str:
    if not recommendations:
        return (
            "实时市场新闻扫描未发现足够明确的股票关注信号。\n\n"
            "免责声明：本报告仅用于舆情事件分析与学习展示，不构成投资建议。"
        )

    lines = [
        "实时市场新闻脉冲",
        "",
        "以下内容是基于最新新闻流、事件情绪、影响强度和风险因子的研究型关注建议，不是买卖指令。",
        "",
        "关注建议",
    ]

    for idx, item in enumerate(recommendations, start=1):
        lines.extend(
            [
                f"{idx}. {item.ticker} - {item.recommendation_type}",
                f"趋势倾向：{item.direction}",
                f"时间窗口：{item.time_window}",
                f"置信度：{item.confidence:.2f}",
                f"风险等级：{item.risk_level}",
                f"理由：{item.rationale}",
            ]
        )
        if item.watch_points:
            lines.append("观察点：")
            lines.extend([f"- {point}" for point in item.watch_points])
        if item.risk_flags:
            lines.append(f"风险标记：{', '.join(item.risk_flags)}")
        lines.append("")

    if trends:
        lines.append("趋势榜")
        for trend in trends[:10]:
            lines.append(
                f"- {trend.ticker}: {trend.direction}, 影响强度 {trend.impact_score:.2f}, 新闻数 {trend.news_count}"
            )
        lines.append("")

    lines.append("免责声明：本报告仅用于舆情事件分析与学习展示，不构成投资建议。")
    return "\n".join(lines)


def _direction_from_score(score: float) -> str:
    if score >= 0.18:
        return "偏正面"
    if score <= -0.18:
        return "偏负面"
    return "中性/观望"


def _build_recommendation_rationale(trend: TickerTrend) -> str:
    if trend.reasons:
        return trend.reasons[0]
    return (
        f"{trend.ticker} 在最新新闻流中出现 {trend.news_count} 条相关信号，"
        f"综合趋势为{trend.direction}。"
    )


def _max_risk(current: str, candidate: str) -> str:
    rank = {"low": 0, "medium": 1, "high": 2}
    return candidate if rank.get(candidate, 0) > rank.get(current, 0) else current


def _extract_report_title(report: str) -> str:
    first_line = report.strip().splitlines()[0] if report.strip() else ""
    return first_line[:120]


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
