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
        _ensure_reports_columns(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                nickname TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watchlist_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT,
                note TEXT,
                item_type TEXT NOT NULL DEFAULT 'ticker',
                keyword TEXT,
                display_name TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(watchlist_id, symbol),
                FOREIGN KEY (watchlist_id) REFERENCES watchlists(id)
            )
            """
        )
        _ensure_watchlist_items_columns(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS report_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                impact_analysis TEXT,
                risk_level TEXT,
                tickers TEXT,
                topics TEXT,
                source_name TEXT,
                source_url TEXT,
                published_at TEXT,
                relevance_score REAL,
                FOREIGN KEY (report_id) REFERENCES reports(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS report_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                watchlist_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                job_type TEXT NOT NULL DEFAULT 'manual',
                scheduled_for TEXT,
                started_at TEXT,
                finished_at TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                error_message TEXT,
                report_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (watchlist_id) REFERENCES watchlists(id),
                FOREIGN KEY (report_id) REFERENCES reports(id)
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


def _ensure_watchlist_items_columns(conn: sqlite3.Connection) -> None:
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(watchlist_items)").fetchall()
    }
    columns = {
        "item_type": "TEXT NOT NULL DEFAULT 'ticker'",
        "keyword": "TEXT",
        "display_name": "TEXT",
    }
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE watchlist_items ADD COLUMN {name} {definition}")


def _ensure_reports_columns(conn: sqlite3.Connection) -> None:
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(reports)").fetchall()
    }
    columns = {
        "user_id": "INTEGER",
        "watchlist_id": "INTEGER",
        "title": "TEXT",
        "report_type": "TEXT DEFAULT 'market_pulse'",
    }
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE reports ADD COLUMN {name} {definition}")


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "query": row["query"],
        "news_count": row["news_count"],
        "risk_level": row["risk_level"],
        "summary": row["summary"],
        "created_at": row["created_at"],
    }
