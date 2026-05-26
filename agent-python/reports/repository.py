import json
from typing import Any

from storage.report_store import _connect, init_db


def save_report(
    user_id: int | None,
    watchlist_id: int | None,
    title: str | None,
    query: str,
    summary: str | None,
    risk_level: str | None,
    report_type: str,
    report_json: dict,
    compliance_status: str = "safe",
    disclaimer: str = "",
) -> int:
    init_db()
    payload = json.dumps(report_json, ensure_ascii=False)

    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO reports (
                user_id,
                watchlist_id,
                title,
                query,
                summary,
                risk_level,
                report_type,
                report_json,
                compliance_status,
                disclaimer,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                user_id,
                watchlist_id,
                title,
                query,
                summary or "",
                risk_level or "unknown",
                report_type or "manual",
                payload,
                compliance_status or "safe",
                disclaimer or "",
            ),
        )
        conn.commit()

    return int(cursor.lastrowid)


def save_report_items(report_id: int, items: list[dict[str, Any]]) -> None:
    init_db()
    if not items:
        return

    rows = [
        (
            report_id,
            item.get("title") or "Untitled news",
            item.get("summary"),
            item.get("impact_analysis"),
            item.get("risk_level"),
            _json_or_none(item.get("tickers")),
            _json_or_none(item.get("topics")),
            item.get("source_name"),
            item.get("source_url"),
            item.get("published_at"),
            item.get("relevance_score"),
        )
        for item in items
    ]

    with _connect() as conn:
        conn.executemany(
            """
            INSERT INTO report_items (
                report_id,
                title,
                summary,
                impact_analysis,
                risk_level,
                tickers,
                topics,
                source_name,
                source_url,
                published_at,
                relevance_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()


def list_reports(user_id: int, watchlist_id: int | None = None) -> list[dict[str, Any]]:
    init_db()
    params: list[Any] = [user_id]
    watchlist_filter = ""
    if watchlist_id is not None:
        watchlist_filter = "AND watchlist_id = ?"
        params.append(watchlist_id)

    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, user_id, watchlist_id, title, query, summary, risk_level,
                   report_type, compliance_status, created_at
            FROM reports
            WHERE user_id = ?
            {watchlist_filter}
            ORDER BY created_at DESC, id DESC
            """,
            params,
        ).fetchall()

    return [_report_row_to_dict(row) for row in rows]


def get_report_by_id(user_id: int, report_id: int) -> dict[str, Any] | None:
    init_db()

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, watchlist_id, title, query, summary, risk_level,
                   report_type, report_json, compliance_status, disclaimer, created_at
            FROM reports
            WHERE id = ? AND user_id = ?
            """,
            (report_id, user_id),
        ).fetchone()

    if row is None:
        return None

    result = _report_row_to_dict(row)
    result["report_json"] = json.loads(row["report_json"])
    return result


def list_report_items(report_id: int) -> list[dict[str, Any]]:
    init_db()

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, report_id, title, summary, impact_analysis, risk_level,
                   tickers, topics, source_name, source_url, published_at,
                   relevance_score
            FROM report_items
            WHERE report_id = ?
            ORDER BY id ASC
            """,
            (report_id,),
        ).fetchall()

    return [_item_row_to_dict(row) for row in rows]


def _report_row_to_dict(row) -> dict[str, Any]:
    result = {
        "id": row["id"],
        "user_id": row["user_id"],
        "watchlist_id": row["watchlist_id"],
        "title": row["title"],
        "query": row["query"],
        "summary": row["summary"],
        "risk_level": row["risk_level"],
        "report_type": row["report_type"],
        "created_at": row["created_at"],
    }
    if "compliance_status" in row.keys():
        result["compliance_status"] = row["compliance_status"]
    if "disclaimer" in row.keys():
        result["disclaimer"] = row["disclaimer"]
    return result


def _item_row_to_dict(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "report_id": row["report_id"],
        "title": row["title"],
        "summary": row["summary"],
        "impact_analysis": row["impact_analysis"],
        "risk_level": row["risk_level"],
        "tickers": row["tickers"],
        "topics": row["topics"],
        "source_name": row["source_name"],
        "source_url": row["source_url"],
        "published_at": row["published_at"],
        "relevance_score": row["relevance_score"],
    }


def _json_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)
