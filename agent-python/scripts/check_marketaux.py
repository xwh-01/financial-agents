from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings
from clients.marketaux_client import search_marketaux_news


async def _run(query: str, limit: int) -> None:
    if not settings.marketaux_base_url:
        raise SystemExit("MARKETAUX_BASE_URL is not configured.")
    if not settings.marketaux_api_key:
        raise SystemExit("MARKETAUX_API_KEY is not configured.")

    items = await search_marketaux_news(
        query=query,
        limit=limit,
        language="en",
        translate_to_zh=False,
    )
    print(f"query={query}")
    print(f"rows={len(items)}")
    for item in items[:3]:
        print(f"- [{item.provider}] {item.source}: {item.title[:120]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Marketaux news search.")
    parser.add_argument("--query", default="stock market today")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    asyncio.run(_run(args.query, args.limit))


if __name__ == "__main__":
    main()
