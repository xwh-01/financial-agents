from fastapi import HTTPException

from market_pulse.service import run_langgraph_market_pulse
from reports.service import save_watchlist_report
from storage import watchlist_store


def get_owned_watchlist_with_items(user_id: int, watchlist_id: int) -> tuple[dict, list[dict]]:
    watchlist = watchlist_store.get_watchlist(
        user_id=user_id,
        watchlist_id=watchlist_id,
    )
    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    items = watchlist_store.list_watchlist_items(
        user_id=user_id,
        watchlist_id=watchlist_id,
    )
    if items is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    if not items:
        raise HTTPException(status_code=400, detail="Watchlist has no items")

    return watchlist, items


def build_watchlist_query(watchlist: dict, items: list[dict]) -> str:
    symbols = [item["symbol"] for item in items if item.get("symbol")]
    names = [item["name"] for item in items if item.get("name")]
    focus = ", ".join(symbols + names)
    return f"Market Pulse for watchlist {watchlist['name']}: {focus}"


async def generate_watchlist_report(
    user_id: int,
    watchlist_id: int,
    max_items: int = 5,
) -> tuple[int, dict]:
    watchlist, items = get_owned_watchlist_with_items(
        user_id=user_id,
        watchlist_id=watchlist_id,
    )
    query = build_watchlist_query(watchlist, items)
    result = await run_langgraph_market_pulse(query=query, max_items=max_items)
    report_id = save_watchlist_report(
        user_id=user_id,
        watchlist_id=watchlist_id,
        title=f"{watchlist['name']} Market Pulse",
        query=query,
        result=result,
    )
    result["report_id"] = report_id
    result["user_id"] = user_id
    result["watchlist_id"] = watchlist_id
    return report_id, result
