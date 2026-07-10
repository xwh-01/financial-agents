import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from auth.schemas import UserResponse
from market_pulse.service import run_fresh_opportunity_scan
from reports.service import save_opportunity_report

logger = logging.getLogger(__name__)

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
    try:
        result = await run_fresh_opportunity_scan(limit=req.limit, max_items=req.max_items)
    except Exception as exc:
        logger.error("opportunity scan failed for user=%s: %s", current_user.id, exc)
        raise HTTPException(
            status_code=502,
            detail="News collection or analysis failed. Check RSS/news sources or try again later.",
        ) from exc

    payload = result.model_dump()
    payload["query"] = "fresh financial news opportunity scan"
    payload["workflow"] = "fresh_news_opportunity_scan"
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["title"] = "今日机会扫描"
    payload["disclaimer"] = (
        "本榜单由 AI 基于公开新闻信息生成，只用于筛选值得进一步研究的候选标的，"
        "不构成任何投资建议、买卖建议或收益承诺。"
    )

    try:
        report_id = save_opportunity_report(user_id=current_user.id, result=payload)
        payload["report_id"] = report_id
    except Exception as exc:
        logger.error("failed to save opportunity report for user=%s: %s", current_user.id, exc)
        # Report is generated but couldn't be persisted — still return the payload
        payload["report_id"] = None

    return payload
