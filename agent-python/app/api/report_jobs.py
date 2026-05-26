from fastapi import APIRouter, Depends, HTTPException, Query

from auth.dependencies import get_current_user
from auth.schemas import UserResponse
from report_jobs.schemas import CreateReportJobRequest, ReportJobResponse
from report_jobs.service import (
    create_manual_job_for_watchlist,
    get_user_job,
    list_user_jobs,
    run_job,
)


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
