from fastapi import APIRouter, Depends, HTTPException, Query

from auth.dependencies import get_current_user
from auth.schemas import UserResponse
from reports.schemas import ReportDetailResponse, ReportItemResponse, ReportResponse
from reports.service import (
    get_user_report_detail,
    list_user_report_items,
    list_user_reports,
    list_user_reports_today,
)
from report_jobs import trace_repository


router = APIRouter()


@router.get("/api/reports", response_model=list[ReportResponse])
async def reports_route(
    watchlist_id: int | None = Query(default=None),
    ticker: str | None = Query(default=None),
    date: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_user),
):
    return list_user_reports(
        user_id=current_user.id,
        watchlist_id=watchlist_id,
        ticker=ticker,
        date_str=date,
        limit=limit,
    )


@router.get("/api/reports/today", response_model=list[ReportResponse])
async def reports_today_route(
    watchlist_id: int | None = Query(default=None),
    current_user: UserResponse = Depends(get_current_user),
):
    return list_user_reports_today(
        user_id=current_user.id,
        watchlist_id=watchlist_id,
    )


@router.get("/api/reports/{report_id}", response_model=ReportDetailResponse)
async def report_detail_route(
    report_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    detail = get_user_report_detail(
        user_id=current_user.id,
        report_id=report_id,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Report not found")

    return detail


@router.get("/api/reports/{report_id}/items", response_model=list[ReportItemResponse])
async def report_items_route(
    report_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    items = list_user_report_items(
        user_id=current_user.id,
        report_id=report_id,
    )
    if items is None:
        raise HTTPException(status_code=404, detail="Report not found")

    return items


@router.get("/api/reports/{report_id}/trace")
async def report_trace_route(
    report_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    detail = get_user_report_detail(
        user_id=current_user.id,
        report_id=report_id,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Report not found")

    trace = trace_repository.get_trace_by_report_id(report_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Report trace not found")

    return {
        "trace": trace,
        "steps": trace_repository.list_trace_steps(trace["id"]),
    }
