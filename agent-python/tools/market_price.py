import httpx

from app.config import settings
from app.errors import ExternalServiceNotConfigured, ExternalServiceError


async def fetch_market_history(ticker: str) -> list[dict]:
    """
    从 Alpha Vantage 拉取真实日线行情。

    返回统一格式：
    [
      {"date": "2026-05-15", "close": 100.0, "volume": 1234567}
    ]

    注意：
    - 返回顺序是从新到旧。
    - calculate_returns 按这个顺序计算近 1/3/7 个交易日收益。
    """
    if not settings.market_api_key:
        raise ExternalServiceNotConfigured("MARKET_API_KEY is not configured.")

    if not settings.market_base_url:
        raise ExternalServiceNotConfigured("MARKET_BASE_URL is not configured.")

    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": ticker,
        "apikey": settings.market_api_key,
        "outputsize": "compact",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(settings.market_base_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        return normalize_market_data(data)

    except Exception as exc:
        raise ExternalServiceError(
            f"Market data request failed for {ticker}: {exc}"
        ) from exc


def normalize_market_data(data: dict) -> list[dict]:
    """
    Alpha Vantage TIME_SERIES_DAILY_ADJUSTED 返回字段大概是：

    {
      "Time Series (Daily)": {
        "2026-05-15": {
          "4. close": "...",
          "5. adjusted close": "...",
          "6. volume": "..."
        }
      }
    }

    这里统一转成：
    [
      {"date": "2026-05-15", "close": 100.0, "volume": 1234567}
    ]
    """

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

        result.append(
            {
                "date": str(date)[:10],
                "close": float(close),
                "volume": int(float(volume)),
            }
        )

    # Alpha Vantage 默认通常已经是新到旧，这里再显式排序，保证稳定
    result.sort(key=lambda x: x["date"], reverse=True)

    return result


def calculate_returns(prices: list[dict]) -> dict:
    """
    prices 要求是新到旧：
    prices[0] = 最新交易日
    prices[1] = 前 1 个交易日
    prices[3] = 前 3 个交易日
    prices[7] = 前 7 个交易日

    return_1d = 最新价 / 1日前价格 - 1
    return_3d = 最新价 / 3日前价格 - 1
    return_7d = 最新价 / 7日前价格 - 1
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
