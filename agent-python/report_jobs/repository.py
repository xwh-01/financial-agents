import json
from typing import Any

from storage.report_store import _connect, init_db


PENDING = "pending"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"
DEAD = "dead"
CANCELLED = "cancelled"

PROGRESS_TOTAL = 8

_JOB_COLUMNS = """
    id, user_id, watchlist_id, status, job_type, scheduled_for,
    current_step, progress_current, progress_total, locked_until,
    started_at, finished_at, attempt_count, max_attempts,
    error_message, last_error, report_id, trace_id, cancel_requested,
    metadata_json, created_at, updated_at
"""


def create_report_job(
    user_id: int,
    watchlist_id: int,
    job_type: str,
    scheduled_for: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> int:
    init_db()

    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO report_jobs (
                user_id, watchlist_id, status, job_type, scheduled_for,
                progress_current, progress_total, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                user_id,
                watchlist_id,
                PENDING,
                job_type or "daily",
                scheduled_for,
                PROGRESS_TOTAL,
                _json(metadata),
            ),
        )
        conn.commit()

    return int(cursor.lastrowid)


def get_report_job_by_id(job_id: int) -> dict[str, Any] | None:
    init_db()

    with _connect() as conn:
        row = conn.execute(
            f"""
            SELECT {_JOB_COLUMNS}
            FROM report_jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

    return _job_to_dict(row) if row else None


def list_report_jobs(
    user_id: int,
    watchlist_id: int | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    init_db()
    params: list[Any] = [user_id]
    filters = ["user_id = ?"]
    if watchlist_id is not None:
        filters.append("watchlist_id = ?")
        params.append(watchlist_id)
    if status is not None:
        filters.append("status = ?")
        params.append(status)

    where_sql = " AND ".join(filters)
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT {_JOB_COLUMNS}
            FROM report_jobs
            WHERE {where_sql}
            ORDER BY created_at DESC, id DESC
            """,
            params,
        ).fetchall()

    return [_job_to_dict(row) for row in rows]


def claim_pending_job(job_id: int) -> bool:
    init_db()

    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE report_jobs
            SET status = ?,
                started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP,
                finished_at = NULL,
                current_step = NULL,
                progress_current = 0,
                progress_total = ?,
                locked_until = datetime('now', '+30 minutes'),
                error_message = NULL,
                last_error = NULL,
                cancel_requested = 0
            WHERE id = ? AND status IN (?, ?)
              AND NOT EXISTS (
                  SELECT 1
                  FROM report_jobs AS other
                  WHERE other.watchlist_id = report_jobs.watchlist_id
                    AND other.status = ?
                    AND other.id != report_jobs.id
                  LIMIT 1
              )
            """,
            (RUNNING, PROGRESS_TOTAL, job_id, PENDING, FAILED, RUNNING),
        )
        conn.commit()

    return cursor.rowcount == 1


def mark_job_running(job_id: int) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE report_jobs
            SET status = ?,
                started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP,
                current_step = NULL,
                progress_current = 0,
                progress_total = ?,
                locked_until = datetime('now', '+30 minutes'),
                error_message = NULL,
                last_error = NULL,
                cancel_requested = 0
            WHERE id = ?
            """,
            (RUNNING, PROGRESS_TOTAL, job_id),
        )
        conn.commit()


def mark_job_succeeded(job_id: int, report_id: int) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE report_jobs
            SET status = ?,
                current_step = 'complete',
                progress_current = progress_total,
                locked_until = NULL,
                finished_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP,
                report_id = ?,
                error_message = NULL,
                last_error = NULL,
                cancel_requested = 0
            WHERE id = ?
            """,
            (SUCCEEDED, report_id, job_id),
        )
        conn.commit()


def mark_job_failed(job_id: int, error_message: str) -> None:
    _mark_unsuccessful(job_id, FAILED, error_message)


def mark_job_dead(job_id: int, error_message: str) -> None:
    _mark_unsuccessful(job_id, DEAD, error_message)


def mark_job_cancelled(job_id: int, error_message: str = "cancelled by user") -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE report_jobs
            SET status = ?,
                locked_until = NULL,
                finished_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP,
                error_message = ?,
                last_error = ?,
                cancel_requested = 0
            WHERE id = ?
            """,
            (CANCELLED, error_message[:1000], error_message[:1000], job_id),
        )
        conn.commit()


def cancel_report_job(job_id: int) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, status FROM report_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            return None

        status = row["status"]
        if status == PENDING:
            conn.execute(
                """
                UPDATE report_jobs
                SET status = ?,
                    finished_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP,
                    error_message = ?,
                    last_error = ?,
                    cancel_requested = 0
                WHERE id = ?
                """,
                (CANCELLED, "cancelled by user", "cancelled by user", job_id),
            )
        elif status == RUNNING:
            conn.execute(
                """
                UPDATE report_jobs
                SET cancel_requested = 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (job_id,),
            )
        conn.commit()

    return get_report_job_by_id(job_id)


def create_retry_job(job_id: int) -> int | None:
    source = get_report_job_by_id(job_id)
    if source is None:
        return None
    if source["status"] not in (FAILED, DEAD, CANCELLED):
        raise ValueError(f"Report job cannot retry from status {source['status']}")
    metadata = dict(source.get("metadata") or {})
    metadata["retry_of_job_id"] = job_id
    return create_report_job(
        user_id=source["user_id"],
        watchlist_id=source["watchlist_id"],
        job_type=source["job_type"] or "manual",
        metadata=metadata,
    )


def set_job_trace_id(job_id: int, trace_id: int) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE report_jobs
            SET trace_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (trace_id, job_id),
        )
        conn.commit()


def update_job_progress(
    job_id: int,
    current_step: str,
    progress_current: int,
    progress_total: int = PROGRESS_TOTAL,
) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE report_jobs
            SET current_step = ?,
                progress_current = ?,
                progress_total = ?,
                locked_until = datetime('now', '+30 minutes'),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (current_step, progress_current, progress_total, job_id),
        )
        conn.commit()


def is_cancel_requested(job_id: int) -> bool:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT cancel_requested, status
            FROM report_jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
    return bool(row and (row["cancel_requested"] or row["status"] == CANCELLED))


def find_pending_jobs(
    limit: int = 10,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    init_db()
    safe_limit = max(1, min(limit, 100))
    params: list[Any] = [PENDING, FAILED]
    filters = [
        "status IN (?, ?)",
        "attempt_count < max_attempts",
        "(scheduled_for IS NULL OR scheduled_for <= CURRENT_TIMESTAMP)",
    ]
    if user_id is not None:
        filters.append("user_id = ?")
        params.append(user_id)

    where_sql = " AND ".join(filters)

    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT {_JOB_COLUMNS}
            FROM report_jobs
            WHERE {where_sql}
            ORDER BY COALESCE(scheduled_for, created_at) ASC, id ASC
            LIMIT ?
            """,
            params + [safe_limit],
        ).fetchall()

    return [_job_to_dict(row) for row in rows]


def requeue_stale_running_jobs(stale_seconds: int, user_id: int | None = None) -> int:
    init_db()
    if stale_seconds <= 0:
        return 0

    update_params: list[Any] = [
        DEAD,
        FAILED,
        "Report job timed out and was requeued",
    ]
    filters = [
        "status = ?",
        "started_at IS NOT NULL",
        "datetime(started_at) <= datetime('now', ?)",
        "attempt_count < max_attempts",
    ]
    where_params: list[Any] = [RUNNING, f"-{stale_seconds} seconds"]
    if user_id is not None:
        filters.append("user_id = ?")
        where_params.append(user_id)

    with _connect() as conn:
        cursor = conn.execute(
            f"""
            UPDATE report_jobs
            SET status = CASE
                    WHEN attempt_count + 1 >= max_attempts THEN ?
                    ELSE ?
                END,
                error_message = ?,
                last_error = ?,
                attempt_count = attempt_count + 1,
                finished_at = CURRENT_TIMESTAMP,
                locked_until = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE {' AND '.join(filters)}
            """,
            update_params + ["Report job timed out and was requeued"] + where_params,
        )
        conn.commit()

    return cursor.rowcount


def has_daily_job_today_for_watchlist(watchlist_id: int) -> bool:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM report_jobs
            WHERE watchlist_id = ?
              AND job_type = 'daily'
              AND date(created_at) = date('now', 'localtime')
              AND status IN (?, ?, ?)
            LIMIT 1
            """,
            (watchlist_id, PENDING, RUNNING, SUCCEEDED),
        ).fetchone()
    return row is not None


def has_running_job_for_watchlist(watchlist_id: int) -> bool:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM report_jobs
            WHERE watchlist_id = ? AND status = ?
            LIMIT 1
            """,
            (watchlist_id, RUNNING),
        ).fetchone()
    return row is not None


def _mark_unsuccessful(job_id: int, status: str, error_message: str) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE report_jobs
            SET status = ?, attempt_count = attempt_count + 1,
                finished_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP,
                locked_until = NULL,
                error_message = ?, last_error = ?
            WHERE id = ?
            """,
            (status, error_message[:1000], error_message[:1000], job_id),
        )
        conn.commit()


def _job_to_dict(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "watchlist_id": row["watchlist_id"],
        "status": row["status"],
        "job_type": row["job_type"],
        "scheduled_for": row["scheduled_for"],
        "current_step": row["current_step"],
        "progress_current": row["progress_current"],
        "progress_total": row["progress_total"],
        "locked_until": row["locked_until"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "attempt_count": row["attempt_count"],
        "max_attempts": row["max_attempts"],
        "error_message": row["error_message"],
        "last_error": row["last_error"] or row["error_message"],
        "report_id": row["report_id"],
        "trace_id": row["trace_id"],
        "cancel_requested": bool(row["cancel_requested"]),
        "metadata": _loads(row["metadata_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _json(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _loads(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {"raw": value}
