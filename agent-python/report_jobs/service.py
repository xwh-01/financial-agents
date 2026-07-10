from fastapi import HTTPException

from app.config import settings
from report_jobs import repository
from report_jobs import trace_repository
from report_jobs.schemas import ReportJobResponse
from storage import watchlist_store
from watchlists.service import generate_watchlist_report, get_owned_watchlist_with_items


def create_manual_job_for_watchlist(user_id: int, watchlist_id: int) -> ReportJobResponse:
    _ensure_watchlist_available(user_id=user_id, watchlist_id=watchlist_id)
    job_id = repository.create_report_job(
        user_id=user_id,
        watchlist_id=watchlist_id,
        job_type="manual",
    )
    return _to_response(repository.get_report_job_by_id(job_id))


def list_user_jobs(
    user_id: int,
    watchlist_id: int | None = None,
    status: str | None = None,
) -> list[ReportJobResponse]:
    return [
        _to_response(job)
        for job in repository.list_report_jobs(
            user_id=user_id,
            watchlist_id=watchlist_id,
            status=status,
        )
    ]


def get_user_job(user_id: int, job_id: int) -> ReportJobResponse | None:
    job = repository.get_report_job_by_id(job_id)
    if job is None or job["user_id"] != user_id:
        return None
    return _to_response(job)


def create_daily_jobs_for_all_watchlists() -> int:
    created = 0
    for watchlist in watchlist_store.list_all_watchlists():
        watchlist_id = watchlist["id"]
        if repository.has_running_job_for_watchlist(watchlist_id):
            continue
        if repository.has_daily_job_today_for_watchlist(watchlist_id):
            continue
        repository.create_report_job(
            user_id=watchlist["user_id"],
            watchlist_id=watchlist_id,
            job_type="daily",
        )
        created += 1
    return created


def create_daily_jobs_for_user(user_id: int) -> dict:
    created_ids: list[int] = []
    skipped = 0
    for watchlist in watchlist_store.list_watchlists(user_id=user_id):
        wl_id = watchlist["id"]
        if repository.has_daily_job_today_for_watchlist(wl_id):
            skipped += 1
            continue
        job_id = repository.create_report_job(
            user_id=user_id,
            watchlist_id=wl_id,
            job_type="daily",
        )
        created_ids.append(job_id)
    return {"created": len(created_ids), "skipped": skipped, "job_ids": created_ids}


async def run_job(job_id: int) -> ReportJobResponse:
    job = repository.get_report_job_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Report job not found")

    status = job["status"]
    if status in (repository.SUCCEEDED, repository.DEAD, repository.CANCELLED):
        raise HTTPException(
            status_code=409,
            detail=f"Report job cannot run from status {status}",
        )

    if status in (repository.PENDING, repository.FAILED):
        if not repository.claim_pending_job(job_id):
            raise HTTPException(status_code=409, detail="Report job is already running")
    elif status != repository.RUNNING:
        raise HTTPException(
            status_code=409,
            detail=f"Report job cannot run from status {status}",
        )

    return await _execute_job(job_id)


async def _execute_job(job_id: int) -> ReportJobResponse:
    job = repository.get_report_job_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Report job not found")

    trace_id = trace_repository.create_trace(
        job_id=job_id,
        user_id=job["user_id"],
        watchlist_id=job["watchlist_id"],
    )
    repository.set_job_trace_id(job_id, trace_id)

    try:
        _raise_if_cancelled(job_id)
        get_owned_watchlist_with_items(
            user_id=job["user_id"],
            watchlist_id=job["watchlist_id"],
        )
        report_id, _ = await generate_watchlist_report(
            user_id=job["user_id"],
            watchlist_id=job["watchlist_id"],
            max_items=settings.market_pulse_max_analyze,
            report_job_id=job_id,
            report_trace_id=trace_id,
        )
        repository.mark_job_succeeded(job_id, report_id)
        trace_repository.finish_trace(
            trace_id=trace_id,
            status=trace_repository.SUCCEEDED,
            report_id=report_id,
        )
    except Exception as exc:
        message = str(exc)
        trace_repository.finish_trace(
            trace_id=trace_id,
            status=trace_repository.FAILED,
            error=message,
        )
        if message == "cancelled by user":
            repository.mark_job_cancelled(job_id, message)
        else:
            next_attempt = int(job["attempt_count"] or 0) + 1
            if next_attempt >= int(job["max_attempts"] or 3):
                repository.mark_job_dead(job_id, message)
            else:
                repository.mark_job_failed(job_id, message)
        raise

    return _to_response(repository.get_report_job_by_id(job_id))


def cancel_user_job(user_id: int, job_id: int) -> ReportJobResponse | None:
    job = repository.get_report_job_by_id(job_id)
    if job is None or job["user_id"] != user_id:
        return None
    return _to_response(repository.cancel_report_job(job_id))


def retry_user_job(user_id: int, job_id: int) -> ReportJobResponse | None:
    job = repository.get_report_job_by_id(job_id)
    if job is None or job["user_id"] != user_id:
        return None
    try:
        new_job_id = repository.create_retry_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_response(repository.get_report_job_by_id(int(new_job_id)))


def get_trace_for_user_job(user_id: int, job_id: int) -> dict | None:
    job = repository.get_report_job_by_id(job_id)
    if job is None or job["user_id"] != user_id:
        return None
    trace = trace_repository.get_trace_by_job_id(job_id)
    if trace is None:
        return None
    return {
        "trace": trace,
        "steps": trace_repository.list_trace_steps(trace["id"]),
        "api_calls": trace_repository.list_api_call_stats(trace["id"]),
    }


def _raise_if_cancelled(job_id: int) -> None:
    if repository.is_cancel_requested(job_id):
        raise RuntimeError("cancelled by user")


def _ensure_watchlist_available(user_id: int, watchlist_id: int) -> None:
    if repository.has_running_job_for_watchlist(watchlist_id):
        raise HTTPException(
            status_code=409,
            detail="Watchlist already has a running report job",
        )
    get_owned_watchlist_with_items(user_id=user_id, watchlist_id=watchlist_id)


def _to_response(job: dict | None) -> ReportJobResponse:
    if job is None:
        raise HTTPException(status_code=404, detail="Report job not found")
    return ReportJobResponse(**job)
