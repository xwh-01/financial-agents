"""Minimal verification: auth → watchlist → report_job closed loop.

Usage:
  uvicorn app.main:app --reload          # start server first
  python scripts/verify_closed_loop.py   # then run this
"""
import sys
from uuid import uuid4

import requests  # pip install requests

BASE = "http://127.0.0.1:8000"


def _log(label: str) -> None:
    print(f"\n--- {label} ---")


def verify() -> int:
    session = requests.Session()
    unique = uuid4().hex[:8]
    email = f"test_{unique}@example.com"
    password = "test123456"

    # 1. register
    _log("register")
    r = session.post(
        f"{BASE}/api/auth/register",
        json={"email": email, "password": password},
    )
    if r.status_code not in (200, 201):
        print(f"register failed: {r.status_code} {r.text}")
        return 1
    user = r.json()
    print(f"registered: id={user['id']} email={user['email']}")

    # 2. login
    _log("login")
    r = session.post(
        f"{BASE}/api/auth/login",
        json={"email": email, "password": password},
    )
    if r.status_code != 200:
        print(f"login failed: {r.status_code} {r.text}")
        return 1
    token = r.json()["access_token"]
    assert token, "token should not be empty"
    session.headers["Authorization"] = f"Bearer {token}"
    print(f"token: {token[:20]}...")

    # 3. create watchlist
    _log("create watchlist")
    r = session.post(
        f"{BASE}/api/watchlists",
        json={"name": "test-watchlist"},
    )
    if r.status_code != 201:
        print(f"create watchlist failed: {r.status_code} {r.text}")
        return 1
    wl = r.json()
    print(f"watchlist: id={wl['id']} name={wl['name']}")

    # 4. add item
    _log("add item")
    r = session.post(
        f"{BASE}/api/watchlists/{wl['id']}/items",
        json={"symbol": "AAPL", "name": "Apple Inc."},
    )
    if r.status_code != 201:
        print(f"add item failed: {r.status_code} {r.text}")
        return 1
    item = r.json()
    print(f"item: id={item['id']} symbol={item['symbol']}")

    # 5. create report job (post to /api/watchlists/{wl_id}/report-jobs)
    _log("create report job")
    r = session.post(
        f"{BASE}/api/watchlists/{wl['id']}/report-jobs",
    )
    if r.status_code not in (200, 201):
        print(f"create report job failed: {r.status_code} {r.text}")
        return 1
    job = r.json()
    print(f"job: id={job['id']} status={job['status']}")

    # 6. list report jobs
    _log("list report jobs")
    r = session.get(f"{BASE}/api/report-jobs")
    if r.status_code != 200:
        print(f"list jobs failed: {r.status_code} {r.text}")
        return 1
    jobs = r.json()
    print(f"total jobs: {len(jobs)}")
    for j in jobs:
        print(f"  job id={j['id']} status={j['status']} type={j['job_type']}")

    print("\n=== ALL PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(verify())
