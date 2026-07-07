from fastapi import HTTPException

from market_pulse.trace import REPORT_STEP_ORDER
from market_pulse.service import run_langgraph_market_pulse
from report_jobs import repository as job_repository
from report_jobs import trace_repository
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
    report_job_id: int | None = None,
    report_trace_id: int | None = None,
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

    result = await run_langgraph_market_pulse(
        query=query,
        max_items=max_items,
        tickers=tickers,
        report_job_id=report_job_id,
        report_trace_id=report_trace_id,
    )
    _record_job_step(
        report_job_id=report_job_id,
        report_trace_id=report_trace_id,
        step_name="compliance_guard",
        input_count=1,
        output_count=1,
        metadata={
            "guard": "reports.service.apply_report_guard",
            "applied_during": "save_report",
        },
    )
    report_id = _record_job_step(
        report_job_id=report_job_id,
        report_trace_id=report_trace_id,
        step_name="save_report",
        input_count=1,
        output_count=1,
        metadata={"report_type": "watchlist"},
        fn=lambda: save_watchlist_report(
            user_id=user_id,
            watchlist_id=watchlist_id,
            title=f"{watchlist['name']} Market Pulse",
            query=query,
            result=result,
        ),
    )
    result["report_id"] = report_id
    result["user_id"] = user_id
    result["watchlist_id"] = watchlist_id
    return report_id, result


def _record_job_step(
    report_job_id: int | None,
    report_trace_id: int | None,
    step_name: str,
    input_count: int,
    output_count: int | None,
    metadata: dict | None = None,
    fn=None,
):
    if report_job_id is None or report_trace_id is None:
        return fn() if fn else None

    if job_repository.is_cancel_requested(report_job_id):
        raise RuntimeError("cancelled by user")

    job_repository.update_job_progress(
        job_id=report_job_id,
        current_step=step_name,
        progress_current=REPORT_STEP_ORDER.get(step_name, 0),
        progress_total=len(REPORT_STEP_ORDER),
    )
    step_id = trace_repository.start_step(
        trace_id=report_trace_id,
        job_id=report_job_id,
        step_name=step_name,
        metadata=metadata,
    )
    try:
        result = fn() if fn else None
        trace_repository.finish_step(
            step_id=step_id,
            status=trace_repository.SUCCEEDED,
            input_count=input_count,
            output_count=output_count,
            metadata=metadata,
        )
        return result
    except Exception as exc:
        trace_repository.finish_step(
            step_id=step_id,
            status=trace_repository.FAILED,
            input_count=input_count,
            error=str(exc),
            metadata=metadata,
        )
        raise
