from market_pulse.schemas import (
    EntityResult,
    EventResult,
    MarketMetrics,
    ReportResult,
    RiskResult,
    TickerLinks,
)
from clients.llm_client import chat_completion


REPORT_SYSTEM_PROMPT = """
你是一个金融舆情分析报告生成助手。

你的任务是根据结构化分析结果，生成中文舆情事件市场影响分析报告。

报告必须包含以下五个部分：
一、事件摘要
二、关联资产
三、市场表现
四、风险提示
五、免责声明

强制要求：
- 必须包含“不构成投资建议”。
- 不得出现“建议买入”“建议卖出”“推荐买入”“推荐卖出”“必涨”“稳赚”“保证收益”等表达。
- 不要把时间相关性说成因果关系。
- 不要输出交易指令。
"""


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


def build_report_user_prompt(
    entity_result: dict,
    event_result: dict,
    ticker_links: dict,
    market_metrics: dict,
    risk_result: dict,
) -> str:
    return f"""
请基于以下结构化结果生成中文报告。

实体识别结果：
{entity_result}

事件分析结果：
{event_result}

股票关联结果：
{ticker_links}

市场表现结果：
{market_metrics}

风险判断结果：
{risk_result}
"""
