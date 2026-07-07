from __future__ import annotations

from app.core.trace import TraceRecorder
from app.schemas import AgentState, AnalysisReport, DISCLAIMER
from app.services.llm_service import LLMService
from app.services.news_service import NewsService
from app.services.ranking_service import rank_news


class FetchNewsNode:
    name = "FetchNewsNode"

    def __init__(self, news_service: NewsService | None = None) -> None:
        self.news_service = news_service or NewsService()

    async def run(self, state: AgentState, trace: TraceRecorder) -> AgentState:
        span = trace.start_node(
            self.name,
            {"query": state.query, "tickers": state.tickers, "max_items": state.max_items},
        )
        error = None
        try:
            state.raw_news = await self.news_service.fetch_news(
                query=state.query,
                tickers=state.tickers,
                limit=max(state.max_items * 3, 10),
            )
        except Exception as exc:
            error = str(exc)
            state.errors.append(f"{self.name}: {error}")
        trace.finish_node(
            span,
            {"raw_news_count": len(state.raw_news), "errors": len(state.errors)},
            error=error,
        )
        return state


class RankNewsNode:
    name = "RankNewsNode"

    async def run(self, state: AgentState, trace: TraceRecorder) -> AgentState:
        span = trace.start_node(self.name, {"raw_news_count": len(state.raw_news)})
        error = None
        try:
            state.ranked_news = rank_news(
                state.raw_news,
                query=state.query,
                tickers=state.tickers,
            )[: state.max_items]
        except Exception as exc:
            error = str(exc)
            state.errors.append(f"{self.name}: {error}")
        trace.finish_node(
            span,
            {
                "ranked_news_count": len(state.ranked_news),
                "top_score": state.ranked_news[0].impact_score if state.ranked_news else None,
            },
            error=error,
        )
        return state


class AnalyzeImpactNode:
    name = "AnalyzeImpactNode"

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self.llm_service = llm_service or LLMService()

    async def run(self, state: AgentState, trace: TraceRecorder) -> AgentState:
        span = trace.start_node(self.name, {"ranked_news_count": len(state.ranked_news)})
        error = None
        try:
            signals = []
            for item in state.ranked_news:
                signals.append(await self.llm_service.analyze_impact(item))
            state.signals = signals
        except Exception as exc:
            error = str(exc)
            state.errors.append(f"{self.name}: {error}")
        trace.finish_node(
            span,
            {"signals_count": len(state.signals), "errors": len(state.errors)},
            error=error,
            llm_model=self.llm_service.last_model,
            token_usage=self.llm_service.last_token_usage,
        )
        return state


class GenerateReportNode:
    name = "GenerateReportNode"

    async def run(self, state: AgentState, trace: TraceRecorder) -> AgentState:
        span = trace.start_node(self.name, {"signals_count": len(state.signals)})
        error = None
        try:
            state.report = AnalysisReport(
                trace_id=state.trace_id,
                query=state.query,
                total_news=len(state.raw_news),
                analyzed_news_count=len(state.signals),
                risk=_overall_risk(state),
                confidence=_average_confidence(state),
                summary=_build_summary(state),
                signals=state.signals,
                errors=state.errors,
                disclaimer=DISCLAIMER,
            )
        except Exception as exc:
            error = str(exc)
            state.errors.append(f"{self.name}: {error}")
        trace.finish_node(
            span,
            {
                "has_report": state.report is not None,
                "risk": state.report.risk if state.report else None,
            },
            error=error,
        )
        return state


class SaveTraceNode:
    name = "SaveTraceNode"

    async def run(self, state: AgentState, trace: TraceRecorder) -> AgentState:
        span = trace.start_node(self.name, {"events_before_save": len(trace.events)})
        try:
            trace.finish_node(span, {"will_save": True}, error=None)
            state.trace_path = trace.save()
        except Exception as exc:
            state.errors.append(f"{self.name}: {exc}")
            trace.finish_node(span, {"will_save": False}, error=str(exc))
        return state


def _overall_risk(state: AgentState) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    value = "low"
    for signal in state.signals:
        if order.get(signal.risk, 0) > order.get(value, 0):
            value = signal.risk
    return value


def _average_confidence(state: AgentState) -> float:
    if not state.signals:
        return 0.0
    return round(sum(item.confidence for item in state.signals) / len(state.signals), 3)


def _build_summary(state: AgentState) -> str:
    if not state.signals:
        return "No high-impact market news was identified from the available sources."
    return " ".join(
        f"{item.symbol or 'Market'}: {item.summary}" for item in state.signals[:3]
    )

