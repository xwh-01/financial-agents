from fastapi import APIRouter, Depends, HTTPException, Query

from auth.dependencies import get_current_user
from auth.schemas import UserResponse
from report_jobs.schemas import CreateReportJobRequest, ReportJobResponse
from report_jobs.service import (
    cancel_user_job,
    create_daily_jobs_for_user,
    create_manual_job_for_watchlist,
    get_trace_for_user_job,
    get_user_job,
    list_user_jobs,
    retry_user_job,
    run_job,
)
from report_jobs.worker import run_pending_jobs_once


router = APIRouter()


@router.post(
    "/api/watchlists/{watchlist_id}/report-jobs",
    response_model=ReportJobResponse,
)
async def create_report_job_route(
    watchlist_id: int,
    request: CreateReportJobRequest | None = None,
    current_user: UserResponse = Depends(get_current_user),
):
    return create_manual_job_for_watchlist(
        user_id=current_user.id,
        watchlist_id=watchlist_id,
    )


@router.get("/api/report-jobs", response_model=list[ReportJobResponse])
async def list_report_jobs_route(
    watchlist_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    current_user: UserResponse = Depends(get_current_user),
):
    return list_user_jobs(
        user_id=current_user.id,
        watchlist_id=watchlist_id,
        status=status,
    )


@router.get("/api/report-jobs/{job_id}", response_model=ReportJobResponse)
async def get_report_job_route(
    job_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    job = get_user_job(user_id=current_user.id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Report job not found")
    return job


@router.post("/api/report-jobs/{job_id}/run", response_model=ReportJobResponse)
async def run_report_job_route(
    job_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    job = get_user_job(user_id=current_user.id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Report job not found")
    return await run_job(job_id)


@router.post("/api/report-jobs/{job_id}/cancel", response_model=ReportJobResponse)
async def cancel_report_job_route(
    job_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    job = cancel_user_job(user_id=current_user.id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Report job not found")
    return job


@router.post("/api/report-jobs/{job_id}/retry", response_model=ReportJobResponse)
async def retry_report_job_route(
    job_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    job = retry_user_job(user_id=current_user.id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Report job not found")
    return job


@router.get("/api/report-jobs/{job_id}/trace")
async def get_report_job_trace_route(
    job_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    payload = get_trace_for_user_job(user_id=current_user.id, job_id=job_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Report trace not found")
    return payload


@router.post("/api/report-jobs/run-pending-once")
async def run_pending_once_route(
    current_user: UserResponse = Depends(get_current_user),
):
    completed = await run_pending_jobs_once(limit=3, user_id=current_user.id)
    return {"completed": completed}


@router.post("/api/report-jobs/create-daily-once")
async def create_daily_once_route(
    current_user: UserResponse = Depends(get_current_user),
):
    return create_daily_jobs_for_user(user_id=current_user.id)
