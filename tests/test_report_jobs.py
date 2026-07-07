from reports import repository as reports_repository


def test_pending_job_can_be_claimed(sample_user_watchlist):
    from report_jobs import repository

    job_id = repository.create_report_job(
        user_id=sample_user_watchlist["user_id"],
        watchlist_id=sample_user_watchlist["watchlist_id"],
        job_type="manual",
    )

    assert repository.claim_pending_job(job_id) is True
    job = repository.get_report_job_by_id(job_id)
    assert job["status"] == repository.RUNNING
    assert job["started_at"] is not None


def test_running_job_updates_current_step_and_progress(sample_user_watchlist):
    from report_jobs import repository

    job_id = repository.create_report_job(
        user_id=sample_user_watchlist["user_id"],
        watchlist_id=sample_user_watchlist["watchlist_id"],
        job_type="manual",
    )
    repository.claim_pending_job(job_id)
    repository.update_job_progress(job_id, "rank_news", 2, 8)

    job = repository.get_report_job_by_id(job_id)
    assert job["current_step"] == "rank_news"
    assert job["progress_current"] == 2
    assert job["progress_total"] == 8


def test_failed_job_records_last_error(sample_user_watchlist):
    from report_jobs import repository

    job_id = repository.create_report_job(
        user_id=sample_user_watchlist["user_id"],
        watchlist_id=sample_user_watchlist["watchlist_id"],
        job_type="manual",
    )
    repository.mark_job_failed(job_id, "mock failure")

    job = repository.get_report_job_by_id(job_id)
    assert job["status"] == repository.FAILED
    assert job["last_error"] == "mock failure"


def test_succeeded_job_records_finished_at(sample_user_watchlist):
    from report_jobs import repository

    job_id = repository.create_report_job(
        user_id=sample_user_watchlist["user_id"],
        watchlist_id=sample_user_watchlist["watchlist_id"],
        job_type="manual",
    )
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

    repository.mark_job_succeeded(job_id, report_id)

    job = repository.get_report_job_by_id(job_id)
    assert job["status"] == repository.SUCCEEDED
    assert job["finished_at"] is not None
    assert job["progress_current"] == job["progress_total"]


def test_cancelled_job_is_not_claimed(sample_user_watchlist):
    from report_jobs import repository

    job_id = repository.create_report_job(
        user_id=sample_user_watchlist["user_id"],
        watchlist_id=sample_user_watchlist["watchlist_id"],
        job_type="manual",
    )
    repository.cancel_report_job(job_id)

    job = repository.get_report_job_by_id(job_id)
    pending = repository.find_pending_jobs(user_id=sample_user_watchlist["user_id"])
    assert job["status"] == repository.CANCELLED
    assert all(item["id"] != job_id for item in pending)


def test_retry_failed_job_creates_new_job(sample_user_watchlist):
    from report_jobs import repository

    job_id = repository.create_report_job(
        user_id=sample_user_watchlist["user_id"],
        watchlist_id=sample_user_watchlist["watchlist_id"],
        job_type="manual",
    )
    repository.mark_job_failed(job_id, "mock failure")

    retry_id = repository.create_retry_job(job_id)
    retry = repository.get_report_job_by_id(retry_id)

    assert retry_id != job_id
    assert retry["status"] == repository.PENDING
    assert retry["metadata"]["retry_of_job_id"] == job_id
