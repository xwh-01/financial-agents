from collections.abc import Awaitable, Callable
from typing import Any

from market_pulse.agent.director import MarketPulseDirectorAgent
from market_pulse.agent.schemas import (
    AgentAction,
    AgentObservation,
    AgentTraceRun,
    AgentTraceStep,
    TraceStatus,
)
from market_pulse.agent.trace_store import save_trace


State = dict[str, Any]
ToolFunc = Callable[[State], Awaitable[State]]


class MarketPulseAgentRunner:
    def __init__(
        self,
        director: MarketPulseDirectorAgent | None = None,
        tools: dict[str, ToolFunc] | None = None,
        save_traces: bool = True,
    ) -> None:
        self.director = director or MarketPulseDirectorAgent()
        self.tools = tools or _default_tools()
        self.save_traces = save_traces

    async def run(
        self,
        query: str,
        max_items: int = 8,
        tickers: list[str] | None = None,
        max_steps: int = 10,
    ) -> AgentTraceRun:
        state: State = {
            "query": query,
            "max_items": max_items,
            "tickers": tickers or [],
            "error_message": None,
            "compliance_checked": False,
            "risk_review_checked": False,
            "collect_attempts": 0,
        }
        trace = AgentTraceRun(query=query, tickers=tickers or [], max_items=max_items)

        for step_no in range(1, max_steps + 1):
            action = self.director.decide_next_action(state)

            if action.name == "finish":
                trace.steps.append(self._trace_step(step_no, action, state, "Workflow completed."))
                trace.final_result = state.get("result")
                trace.status = self._final_status(state, completed=True)
                self._save(trace)
                return trace

            tool = self.tools.get(action.name)
            if tool is None:
                state["error_message"] = f"No tool registered for action: {action.name}"
                trace.steps.append(self._trace_step(step_no, action, state, state["error_message"], state["error_message"]))
                trace.status = "failed"
                trace.final_result = state.get("result")
                self._save(trace)
                return trace

            try:
                before = self._metrics(state)
                if action.name == "collect_news":
                    state["collect_attempts"] = int(state.get("collect_attempts") or 0) + 1

                await tool(state)
                after = self._metrics(state)
                trace.steps.append(
                    self._trace_step(
                        step_no,
                        action,
                        state,
                        self._observation_summary(action, before, after, state),
                    )
                )
            except Exception as exc:
                state["error_message"] = str(exc)
                trace.steps.append(self._trace_step(step_no, action, state, f"Tool failed: {exc}", str(exc)))
                trace.status = "failed"
                trace.final_result = state.get("result")
                self._save(trace)
                return trace

        trace.status = "failed"
        state["error_message"] = f"Exceeded max_steps={max_steps} before finish."
        trace.steps.append(
            self._trace_step(
                max_steps + 1,
                AgentAction(name="finish", reason="超过最大步数，workflow 未完成。"),
                state,
                state["error_message"],
                state["error_message"],
            )
        )
        trace.final_result = state.get("result")
        self._save(trace)
        return trace

    def _trace_step(
        self,
        step_no: int,
        action: AgentAction,
        state: State,
        summary: str,
        error: str | None = None,
    ) -> AgentTraceStep:
        metrics = self._metrics(state)
        return AgentTraceStep(
            step_no=step_no,
            action=action,
            observation=AgentObservation(summary=summary, metrics=metrics),
            metrics=metrics,
            error=error,
        )

    def _metrics(self, state: State) -> dict[str, Any]:
        return {
            "candidate_news_count": len(state.get("candidate_news") or []),
            "ranked_news_count": len(state.get("ranked_news") or []),
            "selected_news_count": len(state.get("selected_news") or []),
            "analyzed_news_count": len(state.get("analyzed_news") or []),
            "risk_level": state.get("overall_risk_level"),
            "has_result": bool(state.get("result")),
            "has_compliance_checked": bool(state.get("compliance_checked")),
        }

    def _observation_summary(
        self,
        action: AgentAction,
        before: dict[str, Any],
        after: dict[str, Any],
        state: State,
    ) -> str:
        if action.name == "collect_news" and after["candidate_news_count"] < 3:
            return "候选新闻不足，可能需要降级或补充搜索。"
        if action.name == "compliance_guard":
            status = (state.get("result") or {}).get("compliance_status", "unknown")
            return f"合规 guard 已执行，status={status}。"
        changed = [
            f"{key}: {before.get(key)} -> {after.get(key)}"
            for key in before
            if before.get(key) != after.get(key)
        ]
        return "; ".join(changed) if changed else f"{action.name} completed."

    def _final_status(self, state: State, completed: bool) -> TraceStatus:
        if not completed:
            return "failed"
        if state.get("error_message"):
            return "degraded"
        if not state.get("result"):
            return "failed"
        if len(state.get("candidate_news") or []) < 3 or not state.get("analyzed_news"):
            return "degraded"
        return "completed"

    def _save(self, trace: AgentTraceRun) -> None:
        if self.save_traces:
            save_trace(trace)


def _default_tools() -> dict[str, ToolFunc]:
    from market_pulse.agent.tools import (
        tool_analyze_items,
        tool_collect_news,
        tool_compliance_guard,
        tool_generate_report,
        tool_rank_news,
        tool_risk_review,
    )

    return {
        "collect_news": tool_collect_news,
        "rank_news": tool_rank_news,
        "analyze_items": tool_analyze_items,
        "risk_review": tool_risk_review,
        "generate_report": tool_generate_report,
        "compliance_guard": tool_compliance_guard,
    }
