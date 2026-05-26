from fastapi import HTTPException

from report_jobs import repository
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
        repository.create_report_job(
            user_id=watchlist["user_id"],
            watchlist_id=watchlist_id,
            job_type="daily",
        )
        created += 1
    return created


async def run_job(job_id: int) -> ReportJobResponse:
    job = repository.get_report_job_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Report job not found")
    if job["status"] not in (repository.PENDING, repository.FAILED):
        raise HTTPException(
            status_code=409,
            detail=f"Report job cannot run from status {job['status']}",
        )

    if not repository.claim_pending_job(job_id):
        raise HTTPException(status_code=409, detail="Report job is already running")

    try:
        get_owned_watchlist_with_items(
            user_id=job["user_id"],
            watchlist_id=job["watchlist_id"],
        )
        report_id, _ = await generate_watchlist_report(
            user_id=job["user_id"],
            watchlist_id=job["watchlist_id"],
            max_items=5,
        )
        repository.mark_job_succeeded(job_id, report_id)
    except Exception as exc:
        message = str(exc)
        next_attempt = int(job["attempt_count"] or 0) + 1
        if next_attempt >= int(job["max_attempts"] or 3):
            repository.mark_job_dead(job_id, message)
        else:
            repository.mark_job_failed(job_id, message)
        raise

    return _to_response(repository.get_report_job_by_id(job_id))


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
