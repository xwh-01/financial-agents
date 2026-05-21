from fastapi import APIRouter, HTTPException

from market_pulse.service import get_report, list_reports


router = APIRouter()


@router.get("/api/reports")
async def reports_route():
    return list_reports(limit=20)


@router.get("/api/reports/{report_id}")
async def report_detail_route(report_id: int):
    report = get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    return report
