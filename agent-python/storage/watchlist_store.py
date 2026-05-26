import sqlite3
from typing import Any

from storage.report_store import _connect, init_db


def create_watchlist(user_id: int, name: str) -> dict[str, Any]:
    init_db()

    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO watchlists (user_id, name)
            VALUES (?, ?)
            """,
            (user_id, name),
        )
        conn.commit()
        watchlist_id = int(cursor.lastrowid)

    watchlist = get_watchlist(user_id=user_id, watchlist_id=watchlist_id)
    if watchlist is None:
        raise RuntimeError("Created watchlist could not be loaded")
    return watchlist


def list_watchlists(user_id: int) -> list[dict[str, Any]]:
    init_db()

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, name, created_at, updated_at
            FROM watchlists
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()

    return [_watchlist_to_dict(row) for row in rows]


def list_all_watchlists() -> list[dict[str, Any]]:
    init_db()

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, name, created_at, updated_at
            FROM watchlists
            ORDER BY id ASC
            """
        ).fetchall()

    return [_watchlist_to_dict(row) for row in rows]


def get_watchlist(user_id: int, watchlist_id: int) -> dict[str, Any] | None:
    init_db()

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, name, created_at, updated_at
            FROM watchlists
            WHERE id = ? AND user_id = ?
            """,
            (watchlist_id, user_id),
        ).fetchone()

    return _watchlist_to_dict(row) if row else None


def add_watchlist_item(
    user_id: int,
    watchlist_id: int,
    symbol: str,
    name: str | None = None,
    note: str | None = None,
) -> dict[str, Any] | None:
    init_db()

    if get_watchlist(user_id=user_id, watchlist_id=watchlist_id) is None:
        return None

    normalized_symbol = symbol.upper().strip()
    try:
        with _connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO watchlist_items (watchlist_id, symbol, name, note)
                VALUES (?, ?, ?, ?)
                """,
                (watchlist_id, normalized_symbol, name, note),
            )
            conn.commit()
            item_id = int(cursor.lastrowid)
    except sqlite3.IntegrityError:
        with _connect() as conn:
            row = conn.execute(
                """
                SELECT id, watchlist_id, symbol, name, note, created_at
                FROM watchlist_items
                WHERE watchlist_id = ? AND symbol = ?
                """,
                (watchlist_id, normalized_symbol),
            ).fetchone()
        return _item_to_dict(row) if row else None

    return get_watchlist_item(
        user_id=user_id,
        watchlist_id=watchlist_id,
        item_id=item_id,
    )


def list_watchlist_items(user_id: int, watchlist_id: int) -> list[dict[str, Any]] | None:
    init_db()

    if get_watchlist(user_id=user_id, watchlist_id=watchlist_id) is None:
        return None

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, watchlist_id, symbol, name, note, created_at
            FROM watchlist_items
            WHERE watchlist_id = ?
            ORDER BY symbol ASC
            """,
            (watchlist_id,),
        ).fetchall()

    return [_item_to_dict(row) for row in rows]


def get_watchlist_item(
    user_id: int,
    watchlist_id: int,
    item_id: int,
) -> dict[str, Any] | None:
    init_db()

    if get_watchlist(user_id=user_id, watchlist_id=watchlist_id) is None:
        return None

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, watchlist_id, symbol, name, note, created_at
            FROM watchlist_items
            WHERE id = ? AND watchlist_id = ?
            """,
            (item_id, watchlist_id),
        ).fetchone()

    return _item_to_dict(row) if row else None


def delete_watchlist_item(user_id: int, watchlist_id: int, item_id: int) -> bool | None:
    init_db()

    if get_watchlist(user_id=user_id, watchlist_id=watchlist_id) is None:
        return None

    with _connect() as conn:
        cursor = conn.execute(
            """
            DELETE FROM watchlist_items
            WHERE id = ? AND watchlist_id = ?
            """,
            (item_id, watchlist_id),
        )
        conn.commit()

    return cursor.rowcount > 0


def _watchlist_to_dict(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "name": row["name"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _item_to_dict(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "watchlist_id": row["watchlist_id"],
        "symbol": row["symbol"],
        "name": row["name"],
        "note": row["note"],
        "created_at": row["created_at"],
    }
