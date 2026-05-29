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


_TYPE_LABELS: dict[str, str] = {
    "ticker": "tickers",
    "company": "companies",
    "topic": "topics",
    "macro": "macro",
    "commodity": "commodities",
    "custom": "custom",
}

_TYPE_ORDER: tuple[str, ...] = ("tickers", "companies", "topics", "macro", "commodities", "custom")


def build_watchlist_query(watchlist: dict, items: list[dict]) -> str:
    groups: dict[str, list[str]] = {}
    seen: set[str] = set()

    for item in items:
        item_type = item.get("item_type", "ticker")
        label = _TYPE_LABELS.get(item_type, item_type)
        groups.setdefault(label, [])

        if item_type == "ticker":
            terms = [
                (item.get("symbol") or "").strip(),
                (item.get("name") or "").strip(),
                (item.get("keyword") or "").strip(),
                (item.get("display_name") or "").strip(),
            ]
        else:
            terms = [
                (item.get("keyword") or "").strip(),
                (item.get("display_name") or "").strip(),
                (item.get("symbol") or "").strip(),
                (item.get("name") or "").strip(),
            ]
        for term in terms:
            if term and term.lower() not in seen:
                seen.add(term.lower())
                groups[label].append(term)

    lines: list[str] = []
    for label in _TYPE_ORDER:
        if label in groups and groups[label]:
            lines.append(f"{label}: {', '.join(groups[label])}")

    body = "\n".join(lines)
    return f"Market Pulse for watchlist {watchlist['name']}:\n{body}"


async def generate_watchlist_report(
    user_id: int,
    watchlist_id: int,
    max_items: int = 8,
) -> tuple[int, dict]:
    watchlist, items = get_owned_watchlist_with_items(
        user_id=user_id,
        watchlist_id=watchlist_id,
    )
    query = build_watchlist_query(watchlist, items)

    tickers = list({
        item.get("symbol", "").strip().upper()
        for item in items
        if item.get("item_type") == "ticker" and item.get("symbol", "").strip()
    })

    result = await run_langgraph_market_pulse(query=query, max_items=max_items, tickers=tickers)
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
