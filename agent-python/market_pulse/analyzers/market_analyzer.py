"""Market data fetcher with request-level cache and failure tracking.

init_market_cache() must be called at the start of each pipeline run
to clear the cache and failure set for the new request.

The cache is protected by an asyncio.Lock to prevent concurrent tasks
from racing on the check-then-set pattern for the same ticker.
"""

import asyncio

from market_pulse.schemas import MarketMetric, MarketMetrics, TickerLinks
from clients.alpha_vantage_client import calculate_returns, fetch_alpha_vantage_daily

_cache: dict[str, list[dict]] = {}
_failures: set[str] = set()
_lock = asyncio.Lock()


def init_market_cache() -> None:
    _cache.clear()
    _failures.clear()


def get_market_failures() -> list[str]:
    return sorted(_failures)


async def analyze_market(
    ticker_links: TickerLinks,
    published_at: str,
) -> MarketMetrics:
    """
    Fetch market data for all linked tickers via Alpha Vantage.

    Uses a request-level cache (reset by init_market_cache) so each ticker is
    fetched at most once per pipeline run. Failures are tracked in a module-level
    set and skipped on subsequent calls within the same run.

    Also fetches SPY as a benchmark to compute relative returns for each ticker.
    """
    tickers = _dedupe(
        ticker_links.direct_tickers + ticker_links.related_tickers + ticker_links.etfs
    )

    metrics: dict[str, MarketMetric] = {}

    spy_return_3d = None
    spy_prices = _cache.get("SPY")
    if spy_prices is None and "SPY" not in _failures:
        try:
            spy_prices = await fetch_alpha_vantage_daily("SPY")
            _cache["SPY"] = spy_prices
        except Exception as exc:
            _failures.add("SPY")
            print(f"[market-data] SPY fetch failed: {exc}")

    if spy_prices is not None:
        spy_returns = calculate_returns(spy_prices)
        spy_return_3d = spy_returns.get("return_3d")

    for ticker in tickers:
        tk = ticker.upper()
        if tk in _failures:
            metrics[ticker] = MarketMetric()
            continue

        async with _lock:
            prices = _cache.get(tk)
            if prices is not None:
                # Another task already fetched this ticker; use cached data.
                pass

        if prices is None:
            try:
                prices = await fetch_alpha_vantage_daily(ticker)
                async with _lock:
                    _cache[tk] = prices
            except Exception as exc:
                async with _lock:
                    _failures.add(tk)
                print(f"[market-data] {ticker} fetch failed: {exc}")
                metrics[ticker] = MarketMetric()
                continue

        result = calculate_returns(prices)
        return_3d = result.get("return_3d")
        relative_to_spy_3d = None
        if return_3d is not None and spy_return_3d is not None:
            relative_to_spy_3d = return_3d - spy_return_3d

        metrics[ticker] = MarketMetric(
            return_1d=result.get("return_1d"),
            return_3d=return_3d,
            return_7d=result.get("return_7d"),
            volume_change=result.get("volume_change"),
            relative_to_spy_3d=relative_to_spy_3d,
        )

    return MarketMetrics(metrics=metrics)


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
