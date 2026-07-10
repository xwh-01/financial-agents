from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from auth.schemas import UserResponse
from storage import watchlist_store
from watchlists.service import generate_watchlist_report


router = APIRouter()


class WatchlistCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


ITEM_TYPES = frozenset({"ticker", "company", "topic", "macro", "commodity", "custom"})


class WatchlistItemCreateRequest(BaseModel):
    symbol: str | None = None
    name: str | None = None
    note: str | None = None
    item_type: str = Field(default="ticker")
    keyword: str | None = None
    display_name: str | None = None


class WatchlistReportGenerateRequest(BaseModel):
    max_items: int = Field(default=8, ge=1, le=50)


@router.get("/api/watchlists")
async def list_watchlists_route(
    current_user: UserResponse = Depends(get_current_user),
):
    return watchlist_store.list_watchlists(user_id=current_user.id)


@router.post("/api/watchlists", status_code=status.HTTP_201_CREATED)
async def create_watchlist_route(
    request: WatchlistCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    return watchlist_store.create_watchlist(
        user_id=current_user.id,
        name=request.name,
    )


@router.get("/api/watchlists/{watchlist_id}/items")
async def list_watchlist_items_route(
    watchlist_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    items = watchlist_store.list_watchlist_items(
        user_id=current_user.id,
        watchlist_id=watchlist_id,
    )
    if items is None:
        raise _watchlist_not_found()
    return items


@router.post("/api/watchlists/{watchlist_id}/items", status_code=status.HTTP_201_CREATED)
async def add_watchlist_item_route(
    watchlist_id: int,
    request: WatchlistItemCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    if request.item_type not in ITEM_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid item_type: {request.item_type}. "
            f"Must be one of {', '.join(sorted(ITEM_TYPES))}",
        )
    if not (request.keyword or "").strip():
        raise HTTPException(
            status_code=422,
            detail="keyword is required and cannot be empty",
        )
    if request.item_type == "ticker" and not (request.symbol or "").strip():
        raise HTTPException(
            status_code=422,
            detail="symbol is required when item_type is 'ticker'",
        )
    symbol = (request.symbol or request.keyword or "").strip()
    item = watchlist_store.add_watchlist_item(
        user_id=current_user.id,
        watchlist_id=watchlist_id,
        symbol=symbol,
        name=request.name,
        note=request.note,
        item_type=request.item_type,
        keyword=request.keyword,
        display_name=request.display_name,
    )
    if item is None:
        raise _watchlist_not_found()
    return item


@router.delete("/api/watchlists/{watchlist_id}/items/{item_id}")
async def delete_watchlist_item_route(
    watchlist_id: int,
    item_id: int,
    current_user: UserResponse = Depends(get_current_user),
):
    deleted = watchlist_store.delete_watchlist_item(
        user_id=current_user.id,
        watchlist_id=watchlist_id,
        item_id=item_id,
    )
    if deleted is None:
        raise _watchlist_not_found()
    if not deleted:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    return {"deleted": True}


@router.post("/api/watchlists/{watchlist_id}/reports/generate")
async def generate_watchlist_report_route(
    watchlist_id: int,
    request: WatchlistReportGenerateRequest | None = None,
    current_user: UserResponse = Depends(get_current_user),
):
    max_items = request.max_items if request else 8
    _, result = await generate_watchlist_report(
        user_id=current_user.id,
        watchlist_id=watchlist_id,
        max_items=max_items,
    )
    return result


def _watchlist_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Watchlist not found")
