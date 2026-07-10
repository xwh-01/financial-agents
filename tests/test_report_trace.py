import asyncio


def test_run_job_creates_report_trace(sample_user_watchlist, monkeypatch):
    from report_jobs import repository, trace_repository
    from report_jobs.service import run_job
    import watchlists.service as watchlist_service

    async def fake_langgraph(query, max_items=8, tickers=None, report_job_id=None, report_trace_id=None):
        steps = [
            ("collect_news", 0, 3, {}),
            ("rank_news", 3, 2, {"selected_news_count": 2}),
            ("analyze_items", 2, 2, {}),
            ("risk_route", 2, 0, {"overall_risk_level": "low"}),
            ("risk_review", 0, 0, {"skipped": True}),
            ("generate_report", 2, 1, {"model_name": "mock-model"}),
        ]
        for index, (name, input_count, output_count, metadata) in enumerate(steps, start=1):
            repository.update_job_progress(report_job_id, name, index, 8)
            step_id = trace_repository.start_step(
                trace_id=report_trace_id,
                job_id=report_job_id,
                step_name=name,
                metadata=metadata,
            )
            trace_repository.finish_step(
                step_id=step_id,
                status=trace_repository.SUCCEEDED,
                input_count=input_count,
                output_count=output_count,
                metadata=metadata,
            )
        return {
            "status": "completed",
            "query": query,
            "summary": "Mock market observation",
            "risk_level": "low",
            "overall_risk_level": "low",
            "analyzed_news": [],
            "market_signals": [],
            "report": "Mock report. This is not investment advice.",
            "trace_id": "langgraph-mock",
        }

    monkeypatch.setattr(watchlist_service, "run_langgraph_market_pulse", fake_langgraph)
    job_id = repository.create_report_job(
        user_id=sample_user_watchlist["user_id"],
        watchlist_id=sample_user_watchlist["watchlist_id"],
        job_type="manual",
    )

    response = asyncio.run(run_job(job_id))

    assert response.status == repository.SUCCEEDED
    assert response.trace_id is not None
    trace = trace_repository.get_trace_by_job_id(job_id)
    assert trace is not None
    assert trace["status"] == trace_repository.SUCCEEDED
    steps = trace_repository.list_trace_steps(trace["id"])
    names = [step["step_name"] for step in steps]
    for required in ["collect_news", "rank_news", "analyze_items", "generate_report", "save_report"]:
        assert required in names
    assert all(step["status"] == trace_repository.SUCCEEDED for step in steps)


def test_trace_step_failure_records_error(sample_user_watchlist):
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

    step_id = trace_repository.start_step(trace_id, job_id, "analyze_items")
    trace_repository.finish_step(
        step_id,
        trace_repository.FAILED,
        input_count=2,
        output_count=0,
        error="mock analysis failed",
    )

    step = trace_repository.list_trace_steps(trace_id)[0]
    assert step["status"] == trace_repository.FAILED
    assert step["error"] == "mock analysis failed"
    assert step["duration_ms"] is not None


def test_api_call_stats_round_trip(sample_user_watchlist):
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

    trace_repository.save_api_call_stats(
        trace_id=trace_id,
        job_id=job_id,
        report_id=None,
        metrics={
            "marketaux": {"logical_calls": 1, "http_attempts": 2},
            "alpha_vantage": {"logical_calls": 3, "http_attempts": 3},
        },
    )

    stats = trace_repository.list_api_call_stats(trace_id)
    by_provider = {row["provider"]: row for row in stats}
    assert by_provider["marketaux"]["logical_calls"] == 1
    assert by_provider["marketaux"]["http_attempts"] == 2
    assert by_provider["alpha_vantage"]["logical_calls"] == 3


def test_save_api_call_stats_ignores_empty_metrics(sample_user_watchlist):
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

    trace_repository.save_api_call_stats(
        trace_id=trace_id,
        job_id=job_id,
        report_id=None,
        metrics={},
    )

    assert trace_repository.list_api_call_stats(trace_id) == []
