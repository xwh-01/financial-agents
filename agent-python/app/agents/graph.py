from __future__ import annotations

from app.agents.nodes import (
    AnalyzeImpactNode,
    FetchNewsNode,
    GenerateReportNode,
    RankNewsNode,
    SaveTraceNode,
)
from app.core.trace import TraceRecorder
from app.schemas import AgentState, AnalysisReport


class MarketPulseWorkflow:
    """Lightweight, testable workflow for the Market Pulse agent."""

    def __init__(
        self,
        fetch_node: FetchNewsNode | None = None,
        rank_node: RankNewsNode | None = None,
        analyze_node: AnalyzeImpactNode | None = None,
        report_node: GenerateReportNode | None = None,
        save_trace_node: SaveTraceNode | None = None,
    ) -> None:
        self.nodes = [
            fetch_node or FetchNewsNode(),
            rank_node or RankNewsNode(),
            analyze_node or AnalyzeImpactNode(),
            report_node or GenerateReportNode(),
            save_trace_node or SaveTraceNode(),
        ]

    async def run(
        self,
        query: str,
        max_items: int = 8,
        tickers: list[str] | None = None,
    ) -> AgentState:
        trace = TraceRecorder()
        state = AgentState(
            query=query,
            max_items=max(1, min(max_items, 20)),
            tickers=tickers or [],
            trace_id=trace.trace_id,
        )
        for node in self.nodes:
            state = await node.run(state, trace)
        return state


async def run_engineering_market_pulse(
    query: str,
    max_items: int = 8,
    tickers: list[str] | None = None,
) -> dict:
    state = await MarketPulseWorkflow().run(
        query=query,
        max_items=max_items,
        tickers=tickers,
    )
    report = state.report or AnalysisReport(
        trace_id=state.trace_id,
        query=query,
        total_news=len(state.raw_news),
        analyzed_news_count=0,
        errors=state.errors,
    )
    payload = report.model_dump()
    payload["status"] = "completed" if not state.errors else "completed_with_errors"
    payload["trace_path"] = state.trace_path
    payload["workflow"] = "engineering_market_pulse_workflow"
    payload["market_signals"] = [item.model_dump() for item in report.signals]
    payload["report"] = report.summary
    return payload
