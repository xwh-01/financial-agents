from collections import defaultdict
from datetime import datetime, timezone

from clients.llm_client import chat_completion
from market_pulse.schemas import (
    ComplianceResult,
    DailyNewsAnalysis,
    EntityResult,
    EventResult,
    FinancialRecommendation,
    MarketMetrics,
    ReportResult,
    RiskResult,
    TickerLinks,
    TickerTrend,
    WorkflowResult,
)
from safety.report_guard import check_report_safety


REPORT_SYSTEM_PROMPT = """
你是一个金融舆情分析报告生成助手。
你的任务是根据结构化分析结果，生成中文舆情事件市场影响分析报告。
报告必须包含以下五个部分：一、事件摘要；二、关联资产；三、市场表现；四、风险提示；五、免责声明。
强制要求：
- 必须包含“不构成投资建议”。
- 不得出现“建议买入”“建议卖出”“推荐买入”“推荐卖出”“必涨”“稳赚”“保证收益”等表达。
- 不要把时间相关性说成因果关系。
- 不要输出交易指令。
"""

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

EVENT_IMPORTANCE = {
    "earnings": 1.35,
    "macro_policy": 1.25,
    "regulation_risk": 1.25,
    "partnership": 1.15,
    "industry_demand": 1.1,
    "controversy": 1.1,
    "product_plan": 0.95,
    "unknown": 0.75,
}


async def generate_report(
    entity_result: EntityResult,
    event_result: EventResult,
    ticker_links: TickerLinks,
    market_metrics: MarketMetrics,
    risk_result: RiskResult,
) -> ReportResult:
    user_prompt = build_report_user_prompt(
        entity_result.model_dump(),
        event_result.model_dump(),
        ticker_links.model_dump(),
        market_metrics.model_dump(),
        risk_result.model_dump(),
    )

    content = await chat_completion(REPORT_SYSTEM_PROMPT, user_prompt)

    return ReportResult(
        content=content.strip(),
        sections=[
            "事件摘要",
            "关联资产",
            "市场表现",
            "风险提示",
            "免责声明",
        ],
    )


def _legacy_build_report_user_prompt(
    entity_result: dict,
    event_result: dict,
    ticker_links: dict,
    market_metrics: dict,
    risk_result: dict,
) -> str:
    return f"""
请基于以下结构化结果生成中文报告。

实体识别结果：{entity_result}

事件分析结果：{event_result}

股票关联结果：{ticker_links}

市场表现结果：{market_metrics}

风险判断结果：{risk_result}
"""


def check_compliance(report_result: ReportResult) -> ComplianceResult:
    return check_report_safety(report_result.content)


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


def _legacy_build_financial_recommendations(
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
                event_importance=trend.event_importance,
                market_confirmation=trend.market_confirmation,
                confirmation_score=trend.confirmation_score,
                risk_level=trend.risk_level,
                time_window=time_window,
                rationale=rationale,
                watch_points=trend.reasons[:3],
                risk_flags=trend.risk_flags,
            )
        )

    return recommendations


def _legacy_build_market_pulse_report(
    trends: list[TickerTrend],
    recommendations: list[FinancialRecommendation],
    analyzed_news: list[DailyNewsAnalysis] | None = None,
) -> str:
    return _build_structured_market_pulse_report(
        trends,
        recommendations,
        analyzed_news or [],
    )

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
        lines.append("趋势概要")
        for trend in trends[:10]:
            lines.append(
                f"- {trend.ticker}: {trend.direction}, 影响强度 {trend.impact_score:.2f}, 新闻数 {trend.news_count}"
            )
        lines.append("")

    lines.append("免责声明：本报告仅用于舆情事件分析与学习展示，不构成投资建议。")
    return "\n".join(lines)


def _build_structured_market_pulse_report(
    trends: list[TickerTrend],
    recommendations: list[FinancialRecommendation],
    analyzed_news: list[DailyNewsAnalysis] | None = None,
) -> str:
    generated_at = _generated_time_label()
    evidence_items = _build_news_evidence(analyzed_news or [])

    if not recommendations:
        return "\n".join(
            [
                "# Market Pulse 财经新闻简报",
                "",
                f"生成时间：{generated_at}",
                "",
                "## 核心结论",
                "本次实时市场新闻扫描未发现足够明确的股票关注信号。",
                "",
                "可能原因包括：候选新闻相关性不足、新闻数量较少，或当前过滤阈值较高。",
                "",
                "## 最终总结：可能风向与新闻依据",
                "当前缺少足够明确的个股信号，整体风向以观望为主；本轮没有形成可追溯到具体股票的新闻证据链。",
                "",
                "## 免责声明",
                "本报告仅用于公开新闻整理、研究参考和风险提示，不构成投资建议。",
            ]
        )

    lines = [
        "# Market Pulse 财经新闻简报",
        "",
        f"生成时间：{generated_at}",
        "",
        "## 核心结论",
        _build_overall_summary(trends, recommendations),
        "",
        "## 重点关注",
    ]

    for idx, item in enumerate(recommendations[:8], start=1):
        lines.extend(
            [
                "",
                f"{idx}. {item.ticker} - {item.recommendation_type}",
                f"- 趋势倾向：{item.direction}",
                f"- 风险等级：{item.risk_level}",
                f"- 置信度：{item.confidence:.2f}",
                f"- 观察窗口：{item.time_window}",
                f"- 主要理由：{item.rationale}",
            ]
        )
        if item.watch_points:
            lines.append("- 观察点：" + "；".join(item.watch_points[:3]))
        if item.risk_flags:
            lines.append("- 风险标记：" + "；".join(item.risk_flags[:5]))

    if trends:
        lines.extend(["", "## 趋势概要"])
        for trend in trends[:10]:
            lines.append(
                f"- {trend.ticker}: {trend.direction}，影响强度 {trend.impact_score:.2f}，"
                f"置信度 {trend.confidence:.2f}，相关新闻 {trend.news_count} 条。"
            )

    lines.extend(["", "## 最终总结：可能风向与新闻依据"])
    lines.append(_build_final_wind_summary(recommendations))
    for item in recommendations[:6]:
        matched_evidence = _match_news_evidence(item.ticker, evidence_items)
        lines.extend(
            [
                "",
                f"### {item.ticker} 风向：{item.direction}",
                f"- 可能风向：{_wind_label(item)}",
                f"- 分析理由：{item.rationale}",
            ]
        )
        if item.watch_points:
            lines.append("- 关键观察点：" + "；".join(item.watch_points[:3]))
        if matched_evidence:
            lines.append("- 相关新闻与依据：")
            for evidence in matched_evidence[:3]:
                lines.append(
                    f"- 新闻：{evidence['title']} "
                    f"({evidence['url'] or evidence['source'] or 'no link'})"
                )
                lines.append(f"- 理由：{evidence['reason']}")
        else:
            lines.append("- 相关新闻与依据：本轮结构化结果中未保留可引用链接，请结合下方 Sources 继续核对。")

    lines.extend(
        [
            "",
            "## 使用说明",
            "以上内容基于新闻舆情、事件强度、关联股票和风险因子的短期倾向分析，不代表确定性预测。",
            "",
            "## 免责声明",
            "本报告仅用于公开新闻整理、研究参考和风险提示，不构成投资建议、买卖建议或收益承诺。",
        ]
    )
    return "\n".join(lines)


def _build_final_wind_summary(recommendations: list[FinancialRecommendation]) -> str:
    if not recommendations:
        return "当前缺少足够明确的个股信号，整体风向以观望为主。"

    positive = [item.ticker for item in recommendations if "正" in item.direction]
    negative = [item.ticker for item in recommendations if "负" in item.direction]
    high_risk = [item.ticker for item in recommendations if item.risk_level == "high"]

    parts = []
    if positive:
        parts.append("偏正面信号集中在：" + "、".join(positive[:5]))
    if negative:
        parts.append("偏负面信号集中在：" + "、".join(negative[:5]))
    if high_risk:
        parts.append("需要优先复核高风险标的：" + "、".join(high_risk[:5]))
    if not parts:
        parts.append("多数信号仍偏中性，适合继续观察新闻后续发展。")
    return "；".join(parts) + "。"


def _wind_label(item: FinancialRecommendation) -> str:
    if item.risk_level == "high":
        return "风险优先，短期应谨慎观察"
    if "正" in item.direction:
        return "偏正面，但仍需等待后续新闻和市场数据确认"
    if "负" in item.direction:
        return "偏负面，重点观察风险是否扩散"
    return "中性观望，信号强度尚不足以形成明确方向"


def _build_news_evidence(
    analyzed_news: list[DailyNewsAnalysis],
) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []

    for item in analyzed_news:
        analysis = item.analysis_result
        news = item.news
        if analysis is None or news is None:
            continue

        tickers = list(news.matched_tickers)
        links = analysis.ticker_links
        if links:
            tickers.extend(links.direct_tickers)
            tickers.extend(links.related_tickers)
            tickers.extend(links.etfs)

        evidence.append(
            {
                "tickers": set(_dedupe(tickers)),
                "title": news.title or "Untitled news",
                "url": news.url or "",
                "source": news.source or news.provider or "",
                "reason": _build_news_reason(analysis),
            }
        )

    return evidence


def _match_news_evidence(
    ticker: str,
    evidence_items: list[dict[str, object]],
) -> list[dict[str, object]]:
    result = []
    for evidence in evidence_items:
        tickers = evidence.get("tickers") or set()
        if ticker in tickers:
            result.append(evidence)
    return result


def _build_news_reason(result: WorkflowResult) -> str:
    event = result.event_result
    risk = result.risk_result
    parts = []

    if event and event.summary:
        parts.append(event.summary)
    if event:
        parts.append(
            f"事件情绪={event.sentiment}，影响强度={event.impact_score:.2f}，置信度={event.confidence:.2f}"
        )
    if risk and risk.risk_flags:
        parts.append("风险因素=" + "、".join(risk.risk_flags[:4]))
    if not parts and result.report:
        parts.append(_extract_report_title(result.report))

    return "；".join(parts) if parts else "该新闻被分析流程识别为相关信号。"


def _build_overall_summary(
    trends: list[TickerTrend],
    recommendations: list[FinancialRecommendation],
) -> str:
    high_risk_count = sum(1 for item in recommendations if item.risk_level == "high")
    tickers = "、".join(item.ticker for item in recommendations[:5])
    if high_risk_count:
        return (
            f"本次扫描识别到 {len(recommendations)} 个可关注标的，其中 {high_risk_count} 个存在高风险标记。"
            f"优先关注：{tickers}。"
        )
    return (
        f"本次扫描识别到 {len(recommendations)} 个可关注标的。"
        f"主要信号集中在：{tickers}。"
    )


def _generated_time_label() -> str:
    value = datetime.now(timezone.utc).astimezone()
    return value.strftime("%Y-%m-%d %H:%M %Z")


def _build_ticker_trend(ticker: str, results: list[WorkflowResult]) -> TickerTrend:
    weighted_scores: list[float] = []
    confidence_values: list[float] = []
    impact_values: list[float] = []
    event_importance_values: list[float] = []
    confirmation_values: list[float] = []
    confirmation_labels: list[str] = []
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
        event_importance = EVENT_IMPORTANCE.get(event.event_type, 0.8)
        confirmation_score, confirmation_label = _market_confirmation(
            ticker=ticker,
            result=result,
            sentiment=event.sentiment,
        )

        score = sentiment * impact * confidence * event_importance
        if score > 0:
            score = max(0.0, score - penalty)
        elif score < 0:
            score = min(0.0, score + penalty)
        score += confirmation_score

        weighted_scores.append(score)
        confidence_values.append(_clamp(confidence + max(0.0, confirmation_score) * 0.6))
        impact_values.append(_clamp(impact * event_importance))
        event_importance_values.append(event_importance)
        confirmation_values.append(confirmation_score)
        if confirmation_label:
            confirmation_labels.append(confirmation_label)

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
    average_event_importance = (
        sum(event_importance_values) / len(event_importance_values)
        if event_importance_values
        else 1.0
    )
    average_confirmation = (
        sum(confirmation_values) / len(confirmation_values)
        if confirmation_values
        else 0.0
    )

    return TickerTrend(
        ticker=ticker,
        direction=_direction_from_score(average_score),
        confidence=round(_clamp(average_confidence), 2),
        impact_score=round(_clamp(average_impact), 2),
        event_importance=round(_clamp(average_event_importance, 0.0, 1.5), 2),
        market_confirmation=_summarize_confirmation(confirmation_labels),
        confirmation_score=round(average_confirmation, 2),
        risk_level=max_risk_level,
        news_count=len(results),
        reasons=_dedupe(reasons)[:5],
        risk_flags=_dedupe(risk_flags),
        source_titles=_dedupe(source_titles)[:5],
    )


def _direction_from_score(score: float) -> str:
    if score >= 0.18:
        return "偏正面"
    if score <= -0.18:
        return "偏负面"
    return "中性/观望"


def _market_confirmation(
    ticker: str,
    result: WorkflowResult,
    sentiment: str,
) -> tuple[float, str]:
    metrics = result.market_metrics.metrics if result.market_metrics else {}
    metric = metrics.get(ticker)
    if metric is None:
        return 0.0, ""

    score = 0.0
    labels: list[str] = []

    ret_1d = metric.return_1d
    rel_3d = metric.relative_to_spy_3d
    volume_change = metric.volume_change

    if sentiment == "positive":
        if ret_1d is not None and ret_1d > 0.01:
            score += 0.06
            labels.append("1日上涨确认")
        if rel_3d is not None and rel_3d > 0.01:
            score += 0.06
            labels.append("3日跑赢SPY")
    elif sentiment == "negative":
        if ret_1d is not None and ret_1d < -0.01:
            score += 0.06
            labels.append("1日下跌确认")
        if rel_3d is not None and rel_3d < -0.01:
            score += 0.06
            labels.append("3日弱于SPY")

    if volume_change is not None and volume_change > 0.2:
        score += 0.04
        labels.append("成交量放大")

    if not labels and any(v is not None for v in (ret_1d, rel_3d, volume_change)):
        return 0.0, "市场反应未明显确认"
    return min(score, 0.15), "、".join(labels)


def _summarize_confirmation(labels: list[str]) -> str:
    selected = _dedupe([label for label in labels if label])
    if selected:
        return "；".join(selected[:3])
    return "未见明显市场确认或未配置行情数据"


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


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


# Clean report-format overrides. They keep the existing scoring and data flow,
# but present Market Pulse output as a user-facing brief instead of Markdown.
REPORT_SYSTEM_PROMPT = """
你是一个财经新闻影响分析助手。请根据结构化分析结果，生成中文、面向普通用户的事件影响说明。

要求：
1. 不使用 Markdown 标题、代码块或表格。
2. 用自然段说明：事件发生了什么、可能影响哪些资产、影响方向和风险点。
3. 不输出交易指令，不使用“建议买入/卖出”“必涨”“稳赚”“保证收益”等表达。
4. 必须包含“仅供研究参考，不构成投资建议”的免责声明。
"""


def build_report_user_prompt(
    entity_result: dict,
    event_result: dict,
    ticker_links: dict,
    market_metrics: dict,
    risk_result: dict,
) -> str:
    return f"""
请基于以下结构化结果生成一段用户可读的中文影响分析。

实体识别结果：{entity_result}

事件分析结果：{event_result}

股票关联结果：{ticker_links}

市场表现结果：{market_metrics}

风险判断结果：{risk_result}
"""


def build_market_pulse_report(
    trends: list[TickerTrend],
    recommendations: list[FinancialRecommendation],
    analyzed_news: list[DailyNewsAnalysis] | None = None,
) -> str:
    generated_at = _generated_time_label()
    evidence_items = _build_news_evidence(analyzed_news or [])

    if not recommendations:
        return "\n".join(
            [
                "Market Pulse 财经新闻简报",
                "",
                f"生成时间：{generated_at}",
                "",
                "一、核心结论",
                "本次实时市场新闻扫描没有发现足够明确的个股关注信号。",
                "可能原因是候选新闻相关性不足、新闻数量较少，或当前过滤阈值较高。",
                "",
                "二、可能风向",
                "当前缺少可追溯到具体股票的强信号，整体更适合继续观察后续新闻变化。",
                "",
                "三、说明",
                "本文仅基于公开新闻整理和模型分析，仅供研究参考，不构成投资建议。",
            ]
        )

    lines = [
        "Market Pulse 财经新闻简报",
        "",
        f"生成时间：{generated_at}",
        "",
        "一、核心结论",
        _build_overall_summary(trends, recommendations),
        "",
        "二、重点关注",
    ]

    for idx, item in enumerate(recommendations[:8], start=1):
        watch_points = "；".join(item.watch_points[:3]) if item.watch_points else "暂无额外观察点"
        risk_flags = "；".join(item.risk_flags[:5]) if item.risk_flags else "暂无突出风险标记"
        lines.extend(
            [
                "",
                f"{idx}. {item.ticker}：{item.recommendation_type}",
                f"可能风向：{_wind_label(item)}",
                f"方向判断：{item.direction}，风险等级：{item.risk_level}，置信度：{item.confidence:.2f}。",
                f"观察窗口：{item.time_window}。",
                f"分析理由：{item.rationale}",
                f"观察重点：{watch_points}",
                f"风险提示：{risk_flags}",
            ]
        )

    if trends:
        lines.extend(["", "三、趋势概要"])
        for trend in trends[:10]:
            lines.append(
                f"{trend.ticker}：{trend.direction}，影响强度 {trend.impact_score:.2f}，"
                f"置信度 {trend.confidence:.2f}，关联新闻 {trend.news_count} 条。"
            )

    lines.extend(["", "四、最终总结：可能风向与新闻依据"])
    lines.append(_build_final_wind_summary(recommendations))

    for item in recommendations[:6]:
        matched_evidence = _match_news_evidence(item.ticker, evidence_items)
        lines.extend(
            [
                "",
                f"{item.ticker} 的可能风向：{_wind_label(item)}",
                f"判断理由：{item.rationale}",
            ]
        )
        if item.watch_points:
            lines.append("关键观察点：" + "；".join(item.watch_points[:3]))
        if matched_evidence:
            lines.append("相关新闻依据：")
            for evidence in matched_evidence[:3]:
                title = evidence["title"]
                link = evidence["url"] or evidence["source"] or "暂无链接"
                lines.append(f"新闻：{title}")
                lines.append(f"链接：{link}")
                lines.append(f"采用该新闻作为依据的原因：{evidence['reason']}")
        else:
            lines.append("相关新闻依据：本轮结构化结果中没有保留可引用链接，请结合下方 Sources 继续核对。")

    lines.extend(
        [
            "",
            "五、使用说明",
            "以上内容基于新闻情绪、事件强度、关联股票和风险因子的短期倾向分析，不代表确定性预测。",
            "",
            "六、免责声明",
            "本文仅用于公开新闻整理、研究参考和风险提示，不构成投资建议、买卖建议或收益承诺。",
        ]
    )
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

        recommendations.append(
            FinancialRecommendation(
                ticker=trend.ticker,
                recommendation_type=recommendation_type,
                direction=trend.direction,
                confidence=trend.confidence,
                risk_level=trend.risk_level,
                time_window=time_window,
                rationale=_build_recommendation_rationale(trend),
                watch_points=trend.reasons[:3],
                risk_flags=trend.risk_flags,
            )
        )

    return recommendations


def _direction_from_score(score: float) -> str:
    if score >= 0.18:
        return "偏正面"
    if score <= -0.18:
        return "偏负面"
    return "中性观望"


def _build_recommendation_rationale(trend: TickerTrend) -> str:
    confirmation = ""
    if trend.confirmation_score > 0:
        confirmation = f" 市场确认：{trend.market_confirmation}。"
    if trend.reasons:
        return trend.reasons[0] + confirmation
    return (
        f"{trend.ticker} 在最新新闻流中出现 {trend.news_count} 条相关信号，"
        f"综合判断为{trend.direction}。" + confirmation
    )


def _build_final_wind_summary(recommendations: list[FinancialRecommendation]) -> str:
    if not recommendations:
        return "当前缺少足够明确的个股信号，整体风向以观望为主。"

    positive = [item.ticker for item in recommendations if "正面" in item.direction]
    negative = [item.ticker for item in recommendations if "负面" in item.direction]
    high_risk = [item.ticker for item in recommendations if item.risk_level == "high"]

    parts = []
    if positive:
        parts.append("偏正面信号集中在：" + "、".join(positive[:5]))
    if negative:
        parts.append("偏负面信号集中在：" + "、".join(negative[:5]))
    if high_risk:
        parts.append("需要优先复核高风险标的：" + "、".join(high_risk[:5]))
    if not parts:
        parts.append("多数信号仍偏中性，适合继续观察新闻后续发展")
    return "；".join(parts) + "。"


def _wind_label(item: FinancialRecommendation) -> str:
    if item.risk_level == "high":
        return "风险优先，短期应谨慎观察"
    if "正面" in item.direction:
        return "偏正面，但仍需要后续新闻和市场数据确认"
    if "负面" in item.direction:
        return "偏负面，重点观察风险是否扩散"
    return "中性观望，信号强度暂不足以形成明确方向"


def _build_news_reason(result: WorkflowResult) -> str:
    event = result.event_result
    risk = result.risk_result
    parts = []

    if event and event.summary:
        parts.append(event.summary)
    if event:
        parts.append(
            f"事件情绪为{event.sentiment}，影响强度 {event.impact_score:.2f}，"
            f"置信度 {event.confidence:.2f}"
        )
    if risk and risk.risk_flags:
        parts.append("风险因素包括：" + "、".join(risk.risk_flags[:4]))
    if not parts and result.report:
        parts.append(_extract_report_title(result.report))

    return "；".join(parts) if parts else "该新闻被分析流程识别为相关信号。"


def _build_overall_summary(
    trends: list[TickerTrend],
    recommendations: list[FinancialRecommendation],
) -> str:
    high_risk_count = sum(1 for item in recommendations if item.risk_level == "high")
    tickers = "、".join(item.ticker for item in recommendations[:5])
    if high_risk_count:
        return (
            f"本次扫描识别到 {len(recommendations)} 个可关注标的，其中 "
            f"{high_risk_count} 个存在高风险标记。优先关注：{tickers}。"
        )
    return f"本次扫描识别到 {len(recommendations)} 个可关注标的，主要信号集中在：{tickers}。"


def _generated_time_label() -> str:
    from datetime import timedelta

    value = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    return value.strftime("%Y-%m-%d %H:%M 北京时间")
