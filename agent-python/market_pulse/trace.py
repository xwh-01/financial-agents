import inspect
import json
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TRACE_DIR = Path(__file__).resolve().parents[1] / "storage" / "langgraph_traces"

REPORT_STEP_ORDER = {
    "collect_news": 1,
    "rank_news": 2,
    "analyze_items": 3,
    "risk_route": 4,
    "risk_review": 5,
    "generate_report": 6,
    "compliance_guard": 7,
    "save_report": 8,
}


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
        report_job_id = state.get("report_job_id")
        report_trace_id = state.get("report_trace_id")
        step_id: int | None = None

        try:
            if report_job_id and report_trace_id:
                _raise_if_cancelled(int(report_job_id))
                _update_report_job_progress(int(report_job_id), node_name)
                step_id = _start_report_step(
                    int(report_trace_id),
                    int(report_job_id),
                    node_name,
                    state,
                    input_count,
                )
            maybe_result = fn(state)
            if inspect.isawaitable(maybe_result):
                maybe_result = await maybe_result
            result = dict(maybe_result or {})
            if step_id is not None:
                _finish_report_step(
                    step_id,
                    "succeeded",
                    input_count,
                    _output_count(node_name, result),
                    metadata=_node_metadata(node_name, state, result),
                )
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
            if step_id is not None:
                _finish_report_step(
                    step_id,
                    "failed",
                    input_count,
                    None,
                    error=error_message,
                    metadata={"error_code": error_code},
                )
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


def record_skipped_report_step(
    state: dict[str, Any],
    step_name: str,
    reason: str,
) -> None:
    report_job_id = state.get("report_job_id")
    report_trace_id = state.get("report_trace_id")
    if not report_job_id or not report_trace_id:
        return
    _update_report_job_progress(int(report_job_id), step_name)
    step_id = _start_report_step(
        int(report_trace_id),
        int(report_job_id),
        step_name,
        state,
        input_count=0,
        metadata={"skipped": True, "reason": reason},
    )
    _finish_report_step(
        step_id,
        "succeeded",
        input_count=0,
        output_count=0,
        metadata={"skipped": True, "reason": reason},
    )


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


def _raise_if_cancelled(job_id: int) -> None:
    from report_jobs import repository

    if repository.is_cancel_requested(job_id):
        raise RuntimeError("cancelled by user")


def _update_report_job_progress(job_id: int, step_name: str) -> None:
    from report_jobs import repository

    repository.update_job_progress(
        job_id=job_id,
        current_step=step_name,
        progress_current=REPORT_STEP_ORDER.get(step_name, 0),
        progress_total=len(REPORT_STEP_ORDER),
    )


def _start_report_step(
    trace_id: int,
    job_id: int,
    step_name: str,
    state: dict[str, Any],
    input_count: int,
    metadata: dict[str, Any] | None = None,
) -> int:
    from report_jobs import trace_repository

    payload = {
        "input_count": input_count,
        "query_present": bool(state.get("query")),
        "tickers_count": len(state.get("tickers") or []),
    }
    if metadata:
        payload.update(metadata)
    return trace_repository.start_step(
        trace_id=trace_id,
        job_id=job_id,
        step_name=step_name,
        metadata=payload,
    )


def _finish_report_step(
    step_id: int,
    status: str,
    input_count: int | None,
    output_count: int | None,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    from report_jobs import trace_repository

    trace_repository.finish_step(
        step_id=step_id,
        status=status,
        input_count=input_count,
        output_count=output_count,
        error=error,
        metadata=metadata,
    )


def _node_metadata(
    node_name: str,
    state: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "candidate_news_count": len(result.get("candidate_news") or state.get("candidate_news") or []),
        "selected_news_count": len(result.get("selected_news") or state.get("selected_news") or []),
        "analyzed_news_count": len(result.get("analyzed_news") or state.get("analyzed_news") or []),
    }
    if node_name == "risk_route":
        metadata["overall_risk_level"] = result.get("overall_risk_level") or state.get("overall_risk_level")
    if node_name == "risk_review":
        metadata["risk_review_notes_count"] = len(result.get("risk_review_notes") or [])
    if node_name == "generate_report":
        payload = result.get("result") or {}
        metadata["market_signal_count"] = len(payload.get("market_signals") or [])
        metadata["model_name"] = payload.get("model_name") or "local_or_configured"
        metadata["compliance_status"] = payload.get("compliance_status")
    return metadata
