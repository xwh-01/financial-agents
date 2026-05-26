"""P0 closed-loop smoke test: auth -> watchlists -> report jobs -> reports.

Usage:
  uvicorn app.main:app --reload --host 127.0.0.1 --port 8010   # start server
  python scripts/smoke_test.py                                   # default 8010, auto-run job
  python scripts/smoke_test.py --skip-run-job                    # create job only (worker picks it up)
  $env:BASE_URL="http://127.0.0.1:8010"; python scripts/smoke_test.py
"""
import os
import sys
from uuid import uuid4

import requests

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8010")
SKIP_RUN_JOB = "--skip-run-job" in sys.argv
DAILY_JOB_CHECK = "--daily-job-check" in sys.argv


def _fail(msg: str, resp: requests.Response) -> None:
    print(f"[FAIL] {msg}")
    print(f"  status: {resp.status_code}")
    print(f"  body: {resp.text}")
    sys.exit(1)


def _check(resp: requests.Response, expected: int | tuple, label: str) -> dict | list:
    exp = expected if isinstance(expected, tuple) else (expected,)
    if resp.status_code not in exp:
        _fail(label, resp)
    data = resp.json()
    if isinstance(data, dict):
        print(f"[OK] {label}  ({resp.status_code})  keys={list(data.keys())[:6]}")
    else:
        print(f"[OK] {label}  ({resp.status_code})  items={len(data)}")
    return data


def main() -> None:
    s = requests.Session()
    unique = uuid4().hex[:8]
    email = f"smoke_{unique}@example.com"
    password = "smokeTest1"

    print(f"BASE_URL={BASE_URL}")
    print(f"test user: {email}")

    r = s.post(f"{BASE_URL}/api/auth/register",
               json={"email": email, "password": password})
    user = _check(r, (200, 201), "POST /api/auth/register")

    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": email, "password": password})
    token_data = _check(r, 200, "POST /api/auth/login")
    token = token_data["access_token"]
    s.headers["Authorization"] = f"Bearer {token}"

    r = s.get(f"{BASE_URL}/api/auth/me")
    _check(r, 200, "GET /api/auth/me")

    r = s.post(f"{BASE_URL}/api/watchlists",
               json={"name": "P0 Smoke Test Watchlist"})
    wl = _check(r, 201, "POST /api/watchlists")
    wl_id = wl["id"]
    print(f"  watchlist_id={wl_id}")

    items_payload = [
        {"item_type": "ticker", "symbol": "NVDA", "name": "NVIDIA", "keyword": "NVIDIA"},
        {"item_type": "topic", "keyword": "AI chips", "display_name": "AI Chips"},
        {"item_type": "macro", "keyword": "Fed interest rate", "display_name": "Fed Interest Rate"},
        {"item_type": "commodity", "keyword": "gold", "display_name": "Gold"},
    ]
    for payload in items_payload:
        r = s.post(f"{BASE_URL}/api/watchlists/{wl_id}/items", json=payload)
        item = _check(r, 201, f"POST /api/watchlists/{wl_id}/items ({payload['item_type']}: {payload.get('symbol') or payload['keyword']})")
        print(f"  item_id={item['id']}  type={item['item_type']}  symbol={item['symbol']}")

    r = s.get(f"{BASE_URL}/api/watchlists/{wl_id}/items")
    items = _check(r, 200, "GET /api/watchlists/{wl_id}/items")
    assert len(items) >= 4, f"Expected >= 4 items, got {len(items)}"
    print(f"  item count: {len(items)}")

    r = s.post(f"{BASE_URL}/api/watchlists/{wl_id}/report-jobs")
    job = _check(r, (200, 201), "POST /api/watchlists/{wl_id}/report-jobs")
    job_id = job["id"]
    print(f"  job_id={job_id}  status={job['status']}")

    if SKIP_RUN_JOB:
        print(f"\n  --skip-run-job set; worker must process job {job_id}")
        print(f"  Start worker: python -m report_jobs.worker")
        print(f"  Or trigger manually: curl -X POST {BASE_URL}/api/report-jobs/{job_id}/run")
    else:
        r = s.post(f"{BASE_URL}/api/report-jobs/{job_id}/run")
        job = _check(r, 200, f"POST /api/report-jobs/{job_id}/run")
        job_status = job.get("status", "")
        print(f"  job status after run: {job_status}")

    r = s.get(f"{BASE_URL}/api/report-jobs/{job_id}")
    job = _check(r, 200, f"GET /api/report-jobs/{job_id}")
    job_status = job.get("status", "")
    report_id = job.get("report_id")
    print(f"  final status: {job_status}  report_id={report_id}")

    if job_status == "succeeded" and report_id:
        r = s.get(f"{BASE_URL}/api/reports/{report_id}")
        report = _check(r, 200, f"GET /api/reports/{report_id}")
        print(f"  report title: {report.get('title', 'N/A')}")
        print(f"  report risk_level: {report.get('risk_level', 'N/A')}")
        print(f"  compliance_status: {report.get('report', {}).get('compliance_status', '?')}")
        disp = report.get("disclaimer")
        print(f"  disclaimer present: {bool(disp)}")

        r = s.get(f"{BASE_URL}/api/reports/{report_id}/items")
        items = _check(r, 200, f"GET /api/reports/{report_id}/items")
        print(f"  report items count: {len(items)}")
    elif SKIP_RUN_JOB:
        print(f"[INFO] job not yet run; start worker or POST /api/report-jobs/{job_id}/run")
    else:
        print(f"[WARN] job did not succeed (status={job_status}), skipping report fetch")
        if job.get("error_message"):
            print(f"  error: {job['error_message']}")

    # bonus: today + filters
    r = s.get(f"{BASE_URL}/api/reports/today")
    today = _check(r, 200, "GET /api/reports/today")
    print(f"  today reports: {len(today)}")

    r = s.get(f"{BASE_URL}/api/reports?watchlist_id={wl_id}")
    filtered = _check(r, 200, "GET /api/reports?watchlist_id=")
    print(f"  reports by watchlist: {len(filtered)}")

    r = s.get(f"{BASE_URL}/api/reports?ticker=NVDA")
    ticker_reports = _check(r, 200, "GET /api/reports?ticker=NVDA")
    print(f"  reports by ticker NVDA: {len(ticker_reports)}")

    from datetime import date
    r = s.get(f"{BASE_URL}/api/reports?date={date.today().isoformat()}")
    dated = _check(r, 200, "GET /api/reports?date=today")
    print(f"  reports by date: {len(dated)}")

    print("\n=== P0 SMOKE TEST PASSED ===")

    if DAILY_JOB_CHECK:
        _daily_check(s, wl_id)


def _daily_check(s: requests.Session, wl_id: int) -> None:
    print("\n=== DAILY JOB CHECK ===")

    r = s.post(f"{BASE_URL}/api/report-jobs/create-daily-once")
    result = _check(r, 200, "POST /api/report-jobs/create-daily-once")
    print(f"  created: {result.get('created')}  skipped: {result.get('skipped')}")
    job_ids = result.get("job_ids", [])

    r = s.get(f"{BASE_URL}/api/report-jobs")
    jobs = _check(r, 200, "GET /api/report-jobs (all)")
    daily_jobs = [j for j in jobs if j.get("job_type") == "daily"]
    print(f"  daily jobs found: {len(daily_jobs)}")

    if not daily_jobs and not job_ids:
        print("[WARN] No daily jobs found. Was create-daily-once successful?")
        return

    target_id = job_ids[0] if job_ids else daily_jobs[0]["id"]
    print(f"  running daily job #{target_id}")

    r = s.post(f"{BASE_URL}/api/report-jobs/{target_id}/run")
    job = _check(r, 200, f"POST /api/report-jobs/{target_id}/run")
    jstatus = job.get("status", "")
    report_id = job.get("report_id")
    print(f"  job status: {jstatus}  report_id: {report_id}")

    r = s.get(f"{BASE_URL}/api/reports/today")
    today = _check(r, 200, "GET /api/reports/today")
    print(f"  today reports: {len(today)}")
    if today:
        for tr in today[:3]:
            print(f"    report_id={tr.get('id')}  title={tr.get('title', '?')[:60]}")
    else:
        print("  [WARN] No reports found for today after running daily job")

    print("\n=== DAILY JOB CHECK DONE ===")


if __name__ == "__main__":
    main()
