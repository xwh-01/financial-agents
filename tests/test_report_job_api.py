from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.dependencies import get_current_user
from auth.schemas import UserResponse
from app.api import report_jobs as report_jobs_api
from app.api import reports as reports_api


def _client(user_id: int) -> TestClient:
    app = FastAPI()
    app.include_router(report_jobs_api.router)
    app.include_router(reports_api.router)
    app.dependency_overrides[get_current_user] = lambda: UserResponse(
        id=user_id,
        email="trace@example.com",
        nickname="Trace User",
        status="active",
    )
    return TestClient(app)


def test_get_report_job_returns_progress_and_trace_id(sample_user_watchlist):
    from report_jobs import repository, trace_repository

    job_id = repository.create_report_job(
        user_id=sample_user_watchlist["user_id"],
        watchlist_id=sample_user_watchlist["watchlist_id"],
        job_type="manual",
    )
    trace_id = trace_repository.create_trace(
        job_id=job_id,
        user_id=sample_user_watchlist["user_id"],
        watchlist_id=sample_user_watchlist["watchlist_id"],
    )
    repository.set_job_trace_id(job_id, trace_id)
    repository.update_job_progress(job_id, "collect_news", 1, 8)

    response = _client(sample_user_watchlist["user_id"]).get(f"/api/report-jobs/{job_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["trace_id"] == trace_id
    assert data["current_step"] == "collect_news"
    assert data["progress_current"] == 1


def test_cancel_report_job_api(sample_user_watchlist):
    from report_jobs import repository

    job_id = repository.create_report_job(
        user_id=sample_user_watchlist["user_id"],
        watchlist_id=sample_user_watchlist["watchlist_id"],
        job_type="manual",
    )

    response = _client(sample_user_watchlist["user_id"]).post(
        f"/api/report-jobs/{job_id}/cancel"
    )

    assert response.status_code == 200
    assert response.json()["status"] == repository.CANCELLED


def test_retry_report_job_api(sample_user_watchlist):
    from report_jobs import repository

    job_id = repository.create_report_job(
        user_id=sample_user_watchlist["user_id"],
        watchlist_id=sample_user_watchlist["watchlist_id"],
        job_type="manual",
    )
    repository.mark_job_failed(job_id, "mock failure")

    response = _client(sample_user_watchlist["user_id"]).post(
        f"/api/report-jobs/{job_id}/retry"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] != job_id
    assert data["status"] == repository.PENDING


def test_get_report_job_trace_api(sample_user_watchlist):
    from report_jobs import repository, trace_repository

    job_id = repository.create_report_job(
        user_id=sample_user_watchlist["user_id"],
        watchlist_id=sample_user_watchlist["watchlist_id"],
        job_type="manual",
    )
    trace_id = trace_repository.create_trace(
        job_id=job_id,
        user_id=sample_user_watchlist["user_id"],
        watchlist_id=sample_user_watchlist["watchlist_id"],
    )
    step_id = trace_repository.start_step(trace_id, job_id, "collect_news")
    trace_repository.finish_step(
        step_id,
        trace_repository.SUCCEEDED,
        input_count=0,
        output_count=3,
        metadata={"selected_news_count": 3},
    )

    response = _client(sample_user_watchlist["user_id"]).get(
        f"/api/report-jobs/{job_id}/trace"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["trace"]["id"] == trace_id
    assert data["steps"][0]["step_name"] == "collect_news"
    assert data["steps"][0]["metadata"]["selected_news_count"] == 3


def test_get_report_trace_by_report_id_api(sample_user_watchlist):
    from report_jobs import repository, trace_repository
    from reports import repository as reports_repository

    report_id = reports_repository.save_report(
        user_id=sample_user_watchlist["user_id"],
        watchlist_id=sample_user_watchlist["watchlist_id"],
        title="Mock Report",
        query="NVDA",
        summary="Mock summary",
        risk_level="low",
        report_type="watchlist",
        report_json={"report": "not investment advice"},
    )
    job_id = repository.create_report_job(
        user_id=sample_user_watchlist["user_id"],
        watchlist_id=sample_user_watchlist["watchlist_id"],
        job_type="manual",
    )
    trace_id = trace_repository.create_trace(
        job_id=job_id,
        user_id=sample_user_watchlist["user_id"],
        watchlist_id=sample_user_watchlist["watchlist_id"],
    )
    trace_repository.finish_trace(
        trace_id,
        trace_repository.SUCCEEDED,
        report_id=report_id,
    )

    response = _client(sample_user_watchlist["user_id"]).get(
        f"/api/reports/{report_id}/trace"
    )

    assert response.status_code == 200
    assert response.json()["trace"]["report_id"] == report_id
