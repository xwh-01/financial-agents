from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from auth.schemas import UserResponse
from market_pulse.service import run_fresh_opportunity_scan
from reports.service import save_opportunity_report


router = APIRouter()


class OpportunityScanRequest(BaseModel):
    limit: int = Field(default=160, ge=20, le=300)
    max_items: int = Field(default=10, ge=3, le=10)


@router.post("/api/opportunities/scan")
async def scan_opportunities_route(
    request: OpportunityScanRequest | None = None,
    current_user: UserResponse = Depends(get_current_user),
):
    req = request or OpportunityScanRequest()
    result = await run_fresh_opportunity_scan(limit=req.limit, max_items=req.max_items)

    payload = result.model_dump()
    payload["query"] = "fresh financial news opportunity scan"
    payload["workflow"] = "fresh_news_opportunity_scan"
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["title"] = "今日机会扫描"
    payload["disclaimer"] = (
        "本榜单由 AI 基于公开新闻信息生成，只用于筛选值得进一步研究的候选标的，"
        "不构成任何投资建议、买卖建议或收益承诺。"
    )

    report_id = save_opportunity_report(user_id=current_user.id, result=payload)
    payload["report_id"] = report_id
    return payload
