from typing import Any

from storage.report_store import _connect, init_db


PENDING = "pending"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"
DEAD = "dead"


def create_report_job(
    user_id: int,
    watchlist_id: int,
    job_type: str,
    scheduled_for: str | None = None,
) -> int:
    init_db()

    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO report_jobs (user_id, watchlist_id, status, job_type, scheduled_for)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, watchlist_id, PENDING, job_type or "daily", scheduled_for),
        )
        conn.commit()

    return int(cursor.lastrowid)


def get_report_job_by_id(job_id: int) -> dict[str, Any] | None:
    init_db()

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, watchlist_id, status, job_type, scheduled_for,
                   started_at, finished_at, attempt_count, max_attempts,
                   error_message, report_id, created_at, updated_at
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
            SELECT id, user_id, watchlist_id, status, job_type, scheduled_for,
                   started_at, finished_at, attempt_count, max_attempts,
                   error_message, report_id, created_at, updated_at
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
        job = conn.execute(
            "SELECT watchlist_id FROM report_jobs WHERE id = ? AND status IN (?, ?)",
            (job_id, PENDING, FAILED),
        ).fetchone()
        if job is None:
            return False

        running = conn.execute(
            """
            SELECT 1 FROM report_jobs
            WHERE watchlist_id = ? AND status = ? AND id != ?
            LIMIT 1
            """,
            (job["watchlist_id"], RUNNING, job_id),
        ).fetchone()
        if running is not None:
            return False

        cursor = conn.execute(
            """
            UPDATE report_jobs
            SET status = ?, started_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP,
                error_message = NULL
            WHERE id = ? AND status IN (?, ?)
            """,
            (RUNNING, job_id, PENDING, FAILED),
        )
        conn.commit()

    return cursor.rowcount == 1


def mark_job_running(job_id: int) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE report_jobs
            SET status = ?, started_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP,
                error_message = NULL
            WHERE id = ?
            """,
            (RUNNING, job_id),
        )
        conn.commit()


def mark_job_succeeded(job_id: int, report_id: int) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE report_jobs
            SET status = ?, finished_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP,
                report_id = ?, error_message = NULL
            WHERE id = ?
            """,
            (SUCCEEDED, report_id, job_id),
        )
        conn.commit()


def mark_job_failed(job_id: int, error_message: str) -> None:
    _mark_unsuccessful(job_id, FAILED, error_message)


def mark_job_dead(job_id: int, error_message: str) -> None:
    _mark_unsuccessful(job_id, DEAD, error_message)


def find_pending_jobs(limit: int = 10) -> list[dict[str, Any]]:
    init_db()
    safe_limit = max(1, min(limit, 100))

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, watchlist_id, status, job_type, scheduled_for,
                   started_at, finished_at, attempt_count, max_attempts,
                   error_message, report_id, created_at, updated_at
            FROM report_jobs
            WHERE status IN (?, ?)
              AND attempt_count < max_attempts
              AND (scheduled_for IS NULL OR scheduled_for <= CURRENT_TIMESTAMP)
            ORDER BY COALESCE(scheduled_for, created_at) ASC, id ASC
            LIMIT ?
            """,
            (PENDING, FAILED, safe_limit),
        ).fetchall()

    return [_job_to_dict(row) for row in rows]


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
                error_message = ?
            WHERE id = ?
            """,
            (status, error_message[:1000], job_id),
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
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "attempt_count": row["attempt_count"],
        "max_attempts": row["max_attempts"],
        "error_message": row["error_message"],
        "report_id": row["report_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
