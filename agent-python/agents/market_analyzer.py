from schemas.ticker import TickerLinks
from schemas.market import MarketMetric, MarketMetrics
from tools.market_price import fetch_market_history, calculate_returns


async def analyze_market(
    ticker_links: TickerLinks,
    published_at: str,
) -> MarketMetrics:
    tickers = _dedupe(
        ticker_links.direct_tickers
        + ticker_links.related_tickers
        + ticker_links.etfs
    )

    metrics: dict[str, MarketMetric] = {}

    spy_return_3d = None
    try:
        spy_prices = await fetch_market_history("SPY")
        spy_returns = calculate_returns(spy_prices)
        spy_return_3d = spy_returns.get("return_3d")
    except Exception:
        spy_return_3d = None

    for ticker in tickers:
        try:
            prices = await fetch_market_history(ticker)
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
        except Exception:
            metrics[ticker] = MarketMetric()

    return MarketMetrics(metrics=metrics)


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result