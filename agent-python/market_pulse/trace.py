import inspect
import json
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TRACE_DIR = Path(__file__).resolve().parents[1] / "storage" / "langgraph_traces"


def new_trace_id() -> str:
    return str(uuid.uuid4())


def trace_node(node_name: str, fn: Callable):
    async def _wrapped(state: dict[str, Any]) -> dict[str, Any]:
        trace_id = str(state.get("trace_id") or new_trace_id())
        start = datetime.now(timezone.utc)
        started = time.perf_counter()
        input_count = _input_count(node_name, state)
        error_code = ""
        error_message = ""
        result: dict[str, Any] = {}

        try:
            maybe_result = fn(state)
            if inspect.isawaitable(maybe_result):
                maybe_result = await maybe_result
            result = dict(maybe_result or {})
            return _with_trace_event(
                state=state,
                result=result,
                trace_id=trace_id,
                node_name=node_name,
                start=start,
                started=started,
                input_count=input_count,
                error_code=error_code,
                error_message=error_message,
            )
        except Exception as exc:
            error_code = exc.__class__.__name__
            error_message = str(exc)
            result = {"error_message": error_message}
            traced_result = _with_trace_event(
                state=state,
                result=result,
                trace_id=trace_id,
                node_name=node_name,
                start=start,
                started=started,
                input_count=input_count,
                error_code=error_code,
                error_message=error_message,
            )
            state.update(traced_result)
            raise

    return _wrapped


def save_trace(trace_id: str, events: list[dict[str, Any]]) -> str:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    path = TRACE_DIR / f"{trace_id}.json"
    payload = {
        "trace_id": trace_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "events": events,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _with_trace_event(
    state: dict[str, Any],
    result: dict[str, Any],
    trace_id: str,
    node_name: str,
    start: datetime,
    started: float,
    input_count: int,
    error_code: str,
    error_message: str,
) -> dict[str, Any]:
    end = datetime.now(timezone.utc)
    merged = dict(result)
    event = {
        "trace_id": trace_id,
        "node_name": node_name,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "input_count": input_count,
        "output_count": _output_count(node_name, merged),
        "error_code": error_code,
        "error_message": error_message,
        "retry_count": 0,
    }
    merged["trace_id"] = trace_id
    merged["trace_events"] = list(state.get("trace_events") or []) + [event]
    return merged


def _input_count(node_name: str, state: dict[str, Any]) -> int:
    if node_name == "collect_news":
        return 1 if state.get("query") else 0
    if node_name == "rank_news":
        return len(state.get("candidate_news") or [])
    if node_name == "analyze_items":
        return len(state.get("selected_news") or [])
    if node_name in {"risk_route", "risk_review", "generate_report"}:
        return len(state.get("analyzed_news") or [])
    return 0


def _output_count(node_name: str, result: dict[str, Any]) -> int:
    if node_name == "collect_news":
        return len(result.get("candidate_news") or [])
    if node_name == "rank_news":
        return len(result.get("selected_news") or [])
    if node_name == "analyze_items":
        return len(result.get("analyzed_news") or [])
    if node_name == "risk_review":
        return len(result.get("risk_review_notes") or [])
    if node_name == "generate_report":
        payload = result.get("result") or {}
        return len(payload.get("market_signals") or [])
    return 0
