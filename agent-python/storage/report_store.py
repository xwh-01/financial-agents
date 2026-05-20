import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "reports.db"


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                news_count INTEGER NOT NULL DEFAULT 0,
                risk_level TEXT NOT NULL DEFAULT 'unknown',
                summary TEXT NOT NULL DEFAULT '',
                report_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def save_report(
    query: str,
    news_count: int,
    risk_level: str,
    summary: str,
    report: dict,
) -> int:
    init_db()
    created_at = datetime.now(timezone.utc).isoformat()
    report_json = json.dumps(report, ensure_ascii=False)

    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO reports (
                query,
                news_count,
                risk_level,
                summary,
                report_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                query,
                news_count,
                risk_level or "unknown",
                summary or "",
                report_json,
                created_at,
            ),
        )
        conn.commit()

    return int(cursor.lastrowid)


def list_reports(limit: int = 20) -> list[dict]:
    init_db()
    safe_limit = max(1, min(limit, 100))

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, query, news_count, risk_level, summary, created_at
            FROM reports
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    return [_row_to_dict(row) for row in rows]


def get_report(report_id: int) -> dict | None:
    init_db()

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, query, news_count, risk_level, summary, report_json, created_at
            FROM reports
            WHERE id = ?
            """,
            (report_id,),
        ).fetchone()

    if row is None:
        return None

    result = _row_to_dict(row)
    result["report"] = json.loads(row["report_json"])
    return result


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "query": row["query"],
        "news_count": row["news_count"],
        "risk_level": row["risk_level"],
        "summary": row["summary"],
        "created_at": row["created_at"],
    }
