from market_pulse.schemas import (
    EntityResult,
    EventResult,
    MarketMetrics,
    ReportResult,
    RiskResult,
    TickerLinks,
)
from clients.llm_client import chat_completion
from prompts.report_prompt import REPORT_SYSTEM_PROMPT, build_report_user_prompt


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
