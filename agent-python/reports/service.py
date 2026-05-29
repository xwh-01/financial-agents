import logging
from typing import Any

from reports import repository
from reports.guard import apply_report_guard
from reports.schemas import ReportDetailResponse, ReportItemResponse, ReportResponse

logger = logging.getLogger(__name__)


def save_watchlist_report(
    user_id: int,
    watchlist_id: int,
    title: str,
    query: str,
    result: dict,
) -> int:
    guarded = _apply_guard_safely(result)
    compliance_status = guarded.get("compliance_status", "safe")
    disclaimer = guarded.get("disclaimer", "")

    report_id = repository.save_report(
        user_id=user_id,
        watchlist_id=watchlist_id,
        title=title,
        query=query,
        summary=_extract_summary(guarded),
        risk_level=_extract_risk_level(guarded),
        report_type="watchlist",
        report_json=guarded,
        compliance_status=compliance_status,
        disclaimer=disclaimer,
    )
    repository.save_report_items(
        report_id=report_id,
        items=extract_report_items(guarded),
    )
    return report_id


def list_user_reports(
    user_id: int,
    watchlist_id: int | None = None,
    ticker: str | None = None,
    date_str: str | None = None,
    limit: int = 20,
) -> list[ReportResponse]:
    return [
        ReportResponse(**item)
        for item in repository.list_reports(
            user_id=user_id,
            watchlist_id=watchlist_id,
            ticker=ticker,
            date_str=date_str,
            limit=limit,
        )
    ]


def list_user_reports_today(
    user_id: int,
    watchlist_id: int | None = None,
) -> list[ReportResponse]:
    return [
        ReportResponse(**item)
        for item in repository.list_reports_today(
            user_id=user_id,
            watchlist_id=watchlist_id,
        )
    ]


def get_user_report_detail(user_id: int, report_id: int) -> ReportDetailResponse | None:
    report = repository.get_report_by_id(user_id=user_id, report_id=report_id)
    if report is None:
        return None

    items = repository.list_report_items(report_id=report_id)
    report_json = report.pop("report_json", None)
    disclaimer = report.pop("disclaimer", None)
    if report_json:
        if not disclaimer:
            disclaimer = report_json.get("disclaimer")
        for key in (
            "candidate_news_count",
            "filtered_news_count",
            "analyzed_news_count",
            "overall_risk_level",
            "report",
            "generated_at",
        ):
            report[key] = report_json.get(key)
    return ReportDetailResponse(
        report=ReportResponse(**report),
        items=[ReportItemResponse(**item) for item in items],
        disclaimer=disclaimer,
    )


def _apply_guard_safely(result: dict) -> dict:
    try:
        return apply_report_guard(result)
    except Exception:
        logger.warning("report guard failed, attaching disclaimer only", exc_info=True)
        result["disclaimer"] = (
            "本报告由 AI 基于公开新闻信息生成，"
            "仅用于信息整理、研究参考和风险提示，"
            "不构成任何投资建议、买卖建议或收益承诺。"
            "投资有风险，用户应自行判断并承担决策责任。"
        )
        result["compliance_status"] = "warning"
        return result


def list_user_report_items(user_id: int, report_id: int) -> list[ReportItemResponse] | None:
    report = repository.get_report_by_id(user_id=user_id, report_id=report_id)
    if report is None:
        return None

    return [
        ReportItemResponse(**item)
        for item in repository.list_report_items(report_id=report_id)
    ]


def extract_report_items(result: dict) -> list[dict[str, Any]]:
    raw_items = result.get("analyzed_news") or result.get("analyzed_items") or []
    items = []
    for raw in raw_items:
        try:
            news = raw.get("news") or {}
            analysis = raw.get("analysis_result") or {}
            entity = analysis.get("entity_result") or {}
            event = analysis.get("event_result") or {}
            risk = analysis.get("risk_result") or {}

            tickers = (
                news.get("matched_tickers")
                or entity.get("tickers")
                or (analysis.get("ticker_links") or {}).get("direct_tickers")
                or []
            )
            topics = news.get("matched_topics") or entity.get("topics") or []

            items.append(
                {
                    "title": news.get("title") or "Untitled news",
                    "summary": event.get("summary") or analysis.get("report") or raw.get("error_message"),
                    "impact_analysis": _build_user_facing_impact_analysis(
                        event=event,
                        risk=risk,
                        analysis=analysis,
                    ),
                    "risk_level": risk.get("risk_level"),
                    "tickers": tickers,
                    "topics": topics,
                    "source_name": news.get("source") or news.get("provider"),
                    "source_url": news.get("url"),
                    "published_at": news.get("published_at"),
                    "relevance_score": news.get("relevance_score"),
                }
            )
        except Exception:
            continue
    return items


def _build_user_facing_impact_analysis(
    event: dict[str, Any],
    risk: dict[str, Any],
    analysis: dict[str, Any],
) -> str:
    """Build a concise source-card explanation instead of showing raw report markdown."""
    if not event and not risk:
        report_text = str(analysis.get("report") or "").strip()
        return _plain_text_excerpt(report_text)

    parts = []

    event_type = str(event.get("event_type") or "").strip()
    sentiment = _sentiment_label(str(event.get("sentiment") or ""))
    impact_score = _format_score(event.get("impact_score"))
    confidence = _format_score(event.get("confidence"))

    first_sentence = []
    if event_type:
        first_sentence.append(f"事件类型为{event_type}")
    if sentiment:
        first_sentence.append(f"市场情绪偏{sentiment}")
    if impact_score:
        first_sentence.append(f"影响强度约为 {impact_score}")
    if confidence:
        first_sentence.append(f"置信度约为 {confidence}")
    if first_sentence:
        parts.append("，".join(first_sentence) + "。")

    summary = str(event.get("summary") or "").strip()
    if summary:
        parts.append(f"主要依据是：{summary}")

    risk_level = str(risk.get("risk_level") or "").strip()
    risk_reason = str(risk.get("reason") or "").strip()
    risk_flags = risk.get("risk_flags") or []
    risk_text = []
    if risk_level:
        risk_text.append(f"风险等级为{risk_level}")
    if risk_reason:
        risk_text.append(risk_reason)
    if risk_flags:
        risk_text.append("需要关注：" + "、".join(str(item) for item in risk_flags[:4]))
    if risk_text:
        parts.append("；".join(risk_text) + "。")

    return " ".join(parts).strip() or _plain_text_excerpt(str(analysis.get("report") or ""))


def _plain_text_excerpt(text: str, max_length: int = 240) -> str:
    cleaned = (
        text.replace("#", "")
        .replace("*", "")
        .replace("`", "")
        .replace("\r", "\n")
    )
    lines = [line.strip(" -\t") for line in cleaned.splitlines() if line.strip()]
    result = " ".join(lines)
    return result[: max_length - 3].rstrip() + "..." if len(result) > max_length else result


def _sentiment_label(value: str) -> str:
    mapping = {
        "positive": "正面",
        "negative": "负面",
        "neutral": "中性",
    }
    return mapping.get(value.lower(), value)


def _format_score(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return ""


def _extract_summary(result: dict) -> str:
    summary = str(result.get("summary") or "").strip()
    if summary:
        return summary

    report_text = str(result.get("report") or result.get("final_report") or "").strip()
    if report_text:
        first_line = next((line.strip() for line in report_text.splitlines() if line.strip()), "")
        summary = first_line or " ".join(report_text.split())
        return summary[:177].rstrip() + "..." if len(summary) > 180 else summary

    query = str(result.get("query") or "").strip()
    return f"Market Pulse report for query: {query}" if query else "Market Pulse report"


def _extract_risk_level(result: dict) -> str:
    return str(
        result.get("risk_level")
        or result.get("overall_risk_level")
        or "unknown"
    )
