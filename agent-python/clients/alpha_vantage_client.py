from app.config import settings
from app.errors import ExternalServiceError, ExternalServiceNotConfigured
from clients.retry import get_json_with_retry
from market_pulse.api_metrics import record_logical_call


async def fetch_alpha_vantage_daily(ticker: str) -> list[dict]:
    """
    Fetch Alpha Vantage TIME_SERIES_DAILY data and normalize it.

    Returns newest-to-oldest rows:
    [
      {"date": "2026-05-15", "close": 100.0, "volume": 1234567}
    ]
    """
    if not settings.alpha_vantage_api_key:
        raise ExternalServiceNotConfigured("ALPHA_VANTAGE_API_KEY is not configured.")

    if not settings.alpha_vantage_base_url:
        raise ExternalServiceNotConfigured("ALPHA_VANTAGE_BASE_URL is not configured.")

    record_logical_call("alpha_vantage")

    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": ticker,
        "apikey": settings.alpha_vantage_api_key,
        "outputsize": "compact",
    }

    try:
        data = await get_json_with_retry(
            settings.alpha_vantage_base_url,
            params=params,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_retry_attempts,
            backoff_seconds=settings.llm_retry_backoff_seconds,
            error_type="alpha_vantage_failed",
        )

        return normalize_alpha_vantage_daily(data)

    except Exception as exc:
        raise ExternalServiceError(
            f"Alpha Vantage request failed for {ticker}: {exc}"
        ) from exc


def normalize_alpha_vantage_daily(data: dict) -> list[dict]:
    if "Error Message" in data:
        raise ExternalServiceError(f"Alpha Vantage error: {data['Error Message']}")

    if "Note" in data:
        raise ExternalServiceError(f"Alpha Vantage rate limit: {data['Note']}")

    if "Information" in data:
        raise ExternalServiceError(f"Alpha Vantage info: {data['Information']}")

    raw_series = data.get("Time Series (Daily)")
    if not isinstance(raw_series, dict):
        raise ExternalServiceError(
            f"Alpha Vantage response missing Time Series (Daily): {data}"
        )

    result: list[dict] = []

    for date, item in raw_series.items():
        close = (
            item.get("5. adjusted close") or item.get("4. close") or item.get("close")
        )
        volume = (
            item.get("6. volume") or item.get("5. volume") or item.get("volume") or 0
        )

        if close is None:
            continue

        try:
            close_val = float(close)
            volume_val = _safe_float(volume)
        except (ValueError, TypeError):
            continue

        result.append(
            {
                "date": str(date)[:10],
                "close": close_val,
                "volume": volume_val,
            }
        )

    result.sort(key=lambda x: x["date"], reverse=True)
    return result


def _safe_float(value) -> int:
    """Parse volume-like values, stripping commas and handling non-numeric strings."""
    if value is None:
        return 0
    text = str(value).replace(",", "").strip()
    try:
        return int(float(text))
    except (ValueError, TypeError):
        return 0


def calculate_returns(prices: list[dict]) -> dict:
    """
    Calculate 1/3/7-trading-day returns from newest-to-oldest price rows.
    """
    if len(prices) < 8:
        return {
            "return_1d": None,
            "return_3d": None,
            "return_7d": None,
            "volume_change": None,
        }

    latest = prices[0]
    p1 = prices[1]
    p3 = prices[3]
    p7 = prices[7]

    latest_close = float(latest["close"])
    latest_volume = int(latest.get("volume", 0))

    def calc_return(old: dict) -> float | None:
        old_close = float(old["close"])
        if old_close == 0:
            return None
        return round((latest_close - old_close) / old_close, 6)

    def calc_volume_change(old: dict) -> float | None:
        old_volume = int(old.get("volume", 0))
        if old_volume == 0:
            return None
        return round((latest_volume - old_volume) / old_volume, 6)

    return {
        "return_1d": calc_return(p1),
        "return_3d": calc_return(p3),
        "return_7d": calc_return(p7),
        "volume_change": calc_volume_change(p1),
    }
