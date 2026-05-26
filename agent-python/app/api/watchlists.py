from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from auth.schemas import UserResponse
from storage import watchlist_store
from watchlists.service import generate_watchlist_report


router = APIRouter()


class WatchlistCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class WatchlistItemCreateRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    name: str | None = None
    note: str | None = None


class WatchlistReportGenerateRequest(BaseModel):
    max_items: int = Field(default=5, ge=1, le=20)


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
    item = watchlist_store.add_watchlist_item(
        user_id=current_user.id,
        watchlist_id=watchlist_id,
        symbol=request.symbol,
        name=request.name,
        note=request.note,
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
    max_items = request.max_items if request else 5
    _, result = await generate_watchlist_report(
        user_id=current_user.id,
        watchlist_id=watchlist_id,
        max_items=max_items,
    )
    return result


def _watchlist_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Watchlist not found")
