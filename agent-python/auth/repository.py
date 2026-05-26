import sqlite3
from typing import Any

from storage.report_store import _connect, init_db


def create_user(email: str, password_hash: str, nickname: str | None) -> dict[str, Any]:
    init_db()

    try:
        with _connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (email, password_hash, nickname)
                VALUES (?, ?, ?)
                """,
                (email.lower(), password_hash, nickname),
            )
            conn.commit()
            user_id = int(cursor.lastrowid)
    except sqlite3.IntegrityError as exc:
        raise ValueError("Email already exists") from exc

    user = get_user_by_id(user_id)
    if user is None:
        raise RuntimeError("Created user could not be loaded")
    return user


def get_user_by_email(email: str) -> dict[str, Any] | None:
    init_db()

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, email, password_hash, nickname, status
            FROM users
            WHERE email = ?
            """,
            (email.lower(),),
        ).fetchone()

    return _row_to_dict(row) if row else None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    init_db()

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, email, password_hash, nickname, status
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    return _row_to_dict(row) if row else None


def email_exists(email: str) -> bool:
    init_db()

    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM users WHERE email = ? LIMIT 1",
            (email.lower(),),
        ).fetchone()

    return row is not None


def _row_to_dict(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "email": row["email"],
        "password_hash": row["password_hash"],
        "nickname": row["nickname"],
        "status": row["status"],
    }
