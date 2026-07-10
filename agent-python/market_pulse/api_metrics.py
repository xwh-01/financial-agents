"""Per-request external API call counter.

Uses contextvars to isolate metrics across concurrently running pipelines.
reset_api_metrics() is called once at the start of each LangGraph run, then
clients increment counters as they call external providers.

Two granularities are tracked per provider:
- logical_calls: one per high-level client function call
  (e.g. one search_marketaux_news or one fetch_alpha_vantage_daily).
- http_attempts: one per real outbound HTTP request, including retries.
"""

from contextvars import ContextVar
from copy import deepcopy

_ERROR_TYPE_TO_PROVIDER = {
    "marketaux_failed": "marketaux",
    "alpha_vantage_failed": "alpha_vantage",
    "rss_fetch_failed": "rss",
}

_metrics_ctx: ContextVar[dict[str, dict[str, int]]] = ContextVar(
    "api_metrics", default=None
)


def _init_metrics() -> dict[str, dict[str, int]]:
    return {}


def _get_metrics() -> dict[str, dict[str, int]]:
    m = _metrics_ctx.get()
    if m is None:
        m = _init_metrics()
        _metrics_ctx.set(m)
    return m


def reset_api_metrics() -> None:
    _metrics_ctx.set(_init_metrics())


def _bucket(provider: str) -> dict[str, int]:
    return _get_metrics().setdefault(provider, {"logical_calls": 0, "http_attempts": 0})


def record_logical_call(provider: str) -> None:
    if not provider:
        return
    _bucket(provider)["logical_calls"] += 1


def record_http_attempt(provider: str) -> None:
    if not provider:
        return
    _bucket(provider)["http_attempts"] += 1


def record_http_attempt_for_error_type(error_type: str) -> None:
    provider = _ERROR_TYPE_TO_PROVIDER.get(error_type or "")
    if provider:
        record_http_attempt(provider)


def get_api_metrics() -> dict[str, dict[str, int]]:
    """Return a copy of the current context's metrics dict."""
    return deepcopy(_get_metrics())
