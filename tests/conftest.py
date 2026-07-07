import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = ROOT / "agent-python"
sys.path.insert(0, str(AGENT_ROOT))

if "feedparser" not in sys.modules:
    sys.modules["feedparser"] = types.SimpleNamespace(
        parse=lambda *_args, **_kwargs: types.SimpleNamespace(feed={}, entries=[])
    )


@pytest.fixture
def temp_reports_db(tmp_path):
    from storage import report_store

    report_store.DB_PATH = tmp_path / "reports.db"
    report_store.init_db()
    return report_store.DB_PATH


@pytest.fixture
def sample_user_watchlist(temp_reports_db):
    from storage.report_store import _connect

    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (email, password_hash, nickname)
            VALUES (?, ?, ?)
            """,
            ("trace@example.com", "hash", "Trace User"),
        )
        user_id = int(cursor.lastrowid)
        cursor = conn.execute(
            """
            INSERT INTO watchlists (user_id, name)
            VALUES (?, ?)
            """,
            (user_id, "AI Infrastructure"),
        )
        watchlist_id = int(cursor.lastrowid)
        conn.execute(
            """
            INSERT INTO watchlist_items (watchlist_id, symbol, name, item_type)
            VALUES (?, ?, ?, ?)
            """,
            (watchlist_id, "NVDA", "NVIDIA", "ticker"),
        )
        conn.commit()

    return {"user_id": user_id, "watchlist_id": watchlist_id}
