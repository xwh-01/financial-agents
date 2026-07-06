from pathlib import Path
from typing import Any

from market_pulse.agent.schemas import AgentTraceRun


TRACE_DIR = Path(__file__).resolve().parents[2] / "storage" / "agent_traces"


def save_trace(trace: AgentTraceRun) -> None:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    path = TRACE_DIR / f"{trace.trace_id}.json"
    path.write_text(trace.model_dump_json(indent=2), encoding="utf-8")


def load_trace(trace_id: str) -> AgentTraceRun | None:
    path = TRACE_DIR / f"{trace_id}.json"
    if not path.exists():
        return None
    return AgentTraceRun.model_validate_json(path.read_text(encoding="utf-8"))


def list_traces(limit: int = 20) -> list[dict[str, Any]]:
    if not TRACE_DIR.exists():
        return []

    traces: list[dict[str, Any]] = []
    for path in sorted(TRACE_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        if len(traces) >= limit:
            break
        trace = load_trace(path.stem)
        if trace is None:
            continue
        traces.append(
            {
                "trace_id": trace.trace_id,
                "query": trace.query,
                "tickers": trace.tickers,
                "max_items": trace.max_items,
                "status": trace.status,
                "step_count": len(trace.steps),
            }
        )
    return traces
