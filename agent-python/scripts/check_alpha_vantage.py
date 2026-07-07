from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings
from clients.alpha_vantage_client import calculate_returns, fetch_alpha_vantage_daily


async def _run(symbol: str) -> None:
    if not settings.alpha_vantage_base_url:
        raise SystemExit(
            "ALPHA_VANTAGE_BASE_URL is not configured. "
            "Use https://www.alphavantage.co/query."
        )
    if not settings.alpha_vantage_api_key:
        raise SystemExit("ALPHA_VANTAGE_API_KEY is not configured.")

    prices = await fetch_alpha_vantage_daily(symbol)
    print(f"symbol={symbol}")
    print(f"rows={len(prices)}")
    print(f"latest={prices[:2]}")
    print(f"returns={calculate_returns(prices)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Alpha Vantage TIME_SERIES_DAILY.")
    parser.add_argument("--symbol", default="AAPL")
    args = parser.parse_args()
    asyncio.run(_run(args.symbol.upper()))


if __name__ == "__main__":
    main()
