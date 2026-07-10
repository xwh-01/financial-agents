import json
from datetime import datetime, timezone
from typing import Any

from storage.report_store import _connect, init_db


RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"


def create_trace(job_id: int, user_id: int, watchlist_id: int) -> int:
    init_db()
    started_at = _now()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO report_traces (
                job_id, user_id, watchlist_id, status, started_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, user_id, watchlist_id, RUNNING, started_at, started_at),
        )
        conn.commit()
    return int(cursor.lastrowid)


def finish_trace(
    trace_id: int,
    status: str,
    report_id: int | None = None,
    error: str | None = None,
) -> None:
    init_db()
    finished_at = _now()
    with _connect() as conn:
        row = conn.execute(
            "SELECT started_at FROM report_traces WHERE id = ?",
            (trace_id,),
        ).fetchone()
        duration_ms = _duration_ms(row["started_at"], finished_at) if row else None
        conn.execute(
            """
            UPDATE report_traces
            SET status = ?,
                report_id = COALESCE(?, report_id),
                finished_at = ?,
                total_duration_ms = ?,
                error = ?
            WHERE id = ?
            """,
            (
                status,
                report_id,
                finished_at,
                duration_ms,
                _trim(error),
                trace_id,
            ),
        )
        conn.commit()


def start_step(
    trace_id: int,
    job_id: int,
    step_name: str,
    metadata: dict[str, Any] | None = None,
) -> int:
    init_db()
    started_at = _now()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO report_trace_steps (
                trace_id, job_id, step_name, status, metadata_json, started_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace_id,
                job_id,
                step_name,
                RUNNING,
                _json(metadata),
                started_at,
                started_at,
            ),
        )
        conn.commit()
    return int(cursor.lastrowid)


def finish_step(
    step_id: int,
    status: str,
    input_count: int | None = None,
    output_count: int | None = None,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    init_db()
    finished_at = _now()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT started_at, metadata_json
            FROM report_trace_steps
            WHERE id = ?
            """,
            (step_id,),
        ).fetchone()
        if row is None:
            return
        merged_metadata = _merge_metadata(row["metadata_json"], metadata)
        conn.execute(
            """
            UPDATE report_trace_steps
            SET status = ?,
                input_count = COALESCE(?, input_count),
                output_count = COALESCE(?, output_count),
                duration_ms = ?,
                error = ?,
                metadata_json = ?,
                finished_at = ?
            WHERE id = ?
            """,
            (
                status,
                input_count,
                output_count,
                _duration_ms(row["started_at"], finished_at),
                _trim(error),
                _json(merged_metadata),
                finished_at,
                step_id,
            ),
        )
        conn.commit()


def get_trace_by_job_id(job_id: int) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, job_id, report_id, watchlist_id, user_id, status,
                   started_at, finished_at, total_duration_ms, error, created_at
            FROM report_traces
            WHERE job_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (job_id,),
        ).fetchone()
    return _trace_to_dict(row) if row else None


def get_trace_by_report_id(report_id: int) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, job_id, report_id, watchlist_id, user_id, status,
                   started_at, finished_at, total_duration_ms, error, created_at
            FROM report_traces
            WHERE report_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (report_id,),
        ).fetchone()
    return _trace_to_dict(row) if row else None


def list_trace_steps(trace_id: int) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, trace_id, job_id, step_name, status, input_count,
                   output_count, duration_ms, error, metadata_json,
                   started_at, finished_at, created_at
            FROM report_trace_steps
            WHERE trace_id = ?
            ORDER BY id ASC
            """,
            (trace_id,),
        ).fetchall()
    return [_step_to_dict(row) for row in rows]


def save_api_call_stats(
    trace_id: int,
    job_id: int | None,
    report_id: int | None,
    metrics: dict[str, dict[str, int]],
) -> None:
    init_db()
    if not metrics:
        return

    rows = [
        (
            trace_id,
            job_id,
            report_id,
            provider,
            int(counts.get("logical_calls", 0)),
            int(counts.get("http_attempts", 0)),
        )
        for provider, counts in metrics.items()
    ]

    with _connect() as conn:
        conn.executemany(
            """
            INSERT INTO api_call_stats (
                trace_id, job_id, report_id, provider, logical_calls, http_attempts
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()


def list_api_call_stats(trace_id: int) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT provider, logical_calls, http_attempts
            FROM api_call_stats
            WHERE trace_id = ?
            ORDER BY provider ASC
            """,
            (trace_id,),
        ).fetchall()
    return [
        {
            "provider": row["provider"],
            "logical_calls": row["logical_calls"],
            "http_attempts": row["http_attempts"],
        }
        for row in rows
    ]


def _trace_to_dict(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "job_id": row["job_id"],
        "report_id": row["report_id"],
        "watchlist_id": row["watchlist_id"],
        "user_id": row["user_id"],
        "status": row["status"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "total_duration_ms": row["total_duration_ms"],
        "error": row["error"],
        "created_at": row["created_at"],
    }


def _step_to_dict(row) -> dict[str, Any]:
    metadata = {}
    if row["metadata_json"]:
        try:
            metadata = json.loads(row["metadata_json"])
        except json.JSONDecodeError:
            metadata = {"raw": row["metadata_json"]}
    return {
        "id": row["id"],
        "trace_id": row["trace_id"],
        "job_id": row["job_id"],
        "step_name": row["step_name"],
        "status": row["status"],
        "input_count": row["input_count"],
        "output_count": row["output_count"],
        "duration_ms": row["duration_ms"],
        "error": row["error"],
        "metadata": metadata,
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "created_at": row["created_at"],
    }


def _merge_metadata(
    current_json: str | None,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    current: dict[str, Any] = {}
    if current_json:
        try:
            current = json.loads(current_json)
        except json.JSONDecodeError:
            current = {"raw": current_json}
    if metadata:
        current.update(metadata)
    return current


def _json(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _duration_ms(started_at: str, finished_at: str) -> int:
    start = datetime.fromisoformat(started_at)
    end = datetime.fromisoformat(finished_at)
    return max(0, round((end - start).total_seconds() * 1000))


def _trim(value: str | None) -> str | None:
    return value[:1000] if value else None
