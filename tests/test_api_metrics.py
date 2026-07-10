from clients.retry import get_with_retry
from market_pulse import api_metrics


def test_reset_and_record_logical_calls():
    api_metrics.reset_api_metrics()
    api_metrics.record_logical_call("marketaux")
    api_metrics.record_logical_call("marketaux")
    api_metrics.record_logical_call("alpha_vantage")

    metrics = api_metrics.get_api_metrics()
    assert metrics["marketaux"]["logical_calls"] == 2
    assert metrics["marketaux"]["http_attempts"] == 0
    assert metrics["alpha_vantage"]["logical_calls"] == 1


def test_record_http_attempt_for_error_type_maps_provider():
    api_metrics.reset_api_metrics()
    api_metrics.record_http_attempt_for_error_type("marketaux_failed")
    api_metrics.record_http_attempt_for_error_type("alpha_vantage_failed")
    api_metrics.record_http_attempt_for_error_type("unknown_source")

    metrics = api_metrics.get_api_metrics()
    assert metrics["marketaux"]["http_attempts"] == 1
    assert metrics["alpha_vantage"]["http_attempts"] == 1
    assert "unknown_source" not in metrics


def test_get_api_metrics_returns_copy():
    api_metrics.reset_api_metrics()
    api_metrics.record_logical_call("marketaux")
    snapshot = api_metrics.get_api_metrics()
    snapshot["marketaux"]["logical_calls"] = 999

    assert api_metrics.get_api_metrics()["marketaux"]["logical_calls"] == 1


def test_reset_clears_all_counters():
    api_metrics.record_logical_call("marketaux")
    api_metrics.reset_api_metrics()
    assert api_metrics.get_api_metrics() == {}


def test_http_attempts_counted_on_retry(monkeypatch):
    import asyncio

    import clients.retry as retry_module

    api_metrics.reset_api_metrics()

    class _FakeResponse:
        status_code = 500
        text = "server error"

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return _FakeResponse()

    monkeypatch.setattr(retry_module.httpx, "AsyncClient", _FakeClient)

    async def _run():
        try:
            await get_with_retry(
                "https://example.com",
                max_retries=3,
                backoff_seconds=0,
                error_type="alpha_vantage_failed",
            )
        except Exception:
            pass

    asyncio.run(_run())

    metrics = api_metrics.get_api_metrics()
    assert metrics["alpha_vantage"]["http_attempts"] == 3
