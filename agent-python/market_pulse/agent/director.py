from market_pulse.agent.schemas import AgentAction


class MarketPulseDirectorAgent:
    """Explainable rule-based director for the Market Pulse workflow."""

    min_candidate_news: int = 3

    def decide_next_action(self, state: dict) -> AgentAction:
        candidate_news = state.get("candidate_news") or []
        ranked_news = state.get("ranked_news") or []
        selected_news = state.get("selected_news") or []
        analyzed_news = state.get("analyzed_news") or []
        result = state.get("result")
        compliance_checked = bool(state.get("compliance_checked"))
        risk_review_checked = bool(state.get("risk_review_checked"))
        collect_attempts = int(state.get("collect_attempts") or 0)

        if not candidate_news:
            return AgentAction(
                name="collect_news",
                reason="当前 state 没有 candidate_news，需要先采集公开财经新闻。",
            )

        if len(candidate_news) < self.min_candidate_news and collect_attempts < 2:
            return AgentAction(
                name="collect_news",
                reason="候选新闻不足，需要补充搜索。",
            )

        if candidate_news and (not ranked_news or not selected_news):
            return AgentAction(
                name="rank_news",
                reason="已有 candidate_news，但尚未生成 ranked_news 或 selected_news，需要排序筛选。",
            )

        if selected_news and not analyzed_news:
            return AgentAction(
                name="analyze_items",
                reason="已有 selected_news，但尚未分析新闻影响，需要执行逐条分析。",
            )

        if analyzed_news and (not state.get("overall_risk_level") or not risk_review_checked):
            return AgentAction(
                name="risk_review",
                reason="已有 analyzed_news，需要执行显式风险路由和风险审查，记录高风险或合规提醒。",
            )

        if analyzed_news and not result:
            return AgentAction(
                name="generate_report",
                reason="已有 analyzed_news 和风险结果，但尚未生成最终报告。",
            )

        if result and not compliance_checked:
            return AgentAction(
                name="compliance_guard",
                reason="已有最终报告，但尚未执行合规 guard，需要检查免责声明和投资建议风险表达。",
            )

        if result and compliance_checked:
            return AgentAction(
                name="finish",
                reason="报告已生成且合规 guard 已完成，可以结束 workflow。",
            )

        return AgentAction(
            name="finish",
            reason="当前 state 没有可继续执行的动作，结束 workflow。",
        )
