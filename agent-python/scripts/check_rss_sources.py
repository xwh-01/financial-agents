import asyncio
import json
from pathlib import Path
from typing import Any

import feedparser
import httpx


BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config" / "company_feeds.json"
REQUEST_TIMEOUT_SECONDS = 15
RSS_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.7",
}


async def main() -> None:
    configs = load_company_feeds()
    companies_count = len(configs)
    rss_sources_count = 0
    ok_count = 0
    failed_count = 0
    total_items = 0

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT_SECONDS,
        follow_redirects=True,
    ) as client:
        for config in configs:
            company = str(config.get("company", "")).strip()
            ticker = str(config.get("ticker", "")).strip()
            rss_feeds = as_str_list(config.get("rss_feeds"))
            rss_sources_count += len(rss_feeds)

            print(f"\n[{company} / {ticker}] rss_sources={len(rss_feeds)}")

            for url in rss_feeds:
                result = await check_feed(client, url)
                if result["ok"]:
                    ok_count += 1
                else:
                    failed_count += 1
                total_items += result["items_count"]

                print(
                    f"- {result['status']} "
                    f"http_status={result['http_status']} "
                    f"items={result['items_count']} "
                    f"url={url}"
                )
                if result["error"]:
                    print(f"  error: {result['error']}")
                for title in result["titles"]:
                    print(f"  title: {title}")

    print("\nSummary")
    print(f"companies_count={companies_count}")
    print(f"rss_sources_count={rss_sources_count}")
    print(f"ok_count={ok_count}")
    print(f"failed_count={failed_count}")
    print(f"total_items={total_items}")


def load_company_feeds() -> list[dict[str, Any]]:
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"FAILED to read config: {CONFIG_PATH} error={exc}")
        return []

    if not isinstance(raw, list):
        print(f"FAILED invalid config root, expected list: {CONFIG_PATH}")
        return []

    return [item for item in raw if isinstance(item, dict)]


async def check_feed(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    try:
        response = await client.get(url, headers=RSS_REQUEST_HEADERS)
        http_status = response.status_code
        parsed = feedparser.parse(response.content)
        entries = list(parsed.entries or [])
        titles = [as_text(entry.get("title")) for entry in entries[:3]]
        titles = [title for title in titles if title]
        ok = 200 <= http_status < 300 and len(entries) > 0

        return {
            "ok": ok,
            "status": "OK" if ok else "FAILED",
            "http_status": http_status,
            "items_count": len(entries),
            "titles": titles,
            "error": "" if ok else feed_error(parsed),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "FAILED",
            "http_status": "N/A",
            "items_count": 0,
            "titles": [],
            "error": str(exc),
        }


def feed_error(parsed) -> str:
    if getattr(parsed, "bozo", False):
        return str(getattr(parsed, "bozo_exception", "feed parse error"))
    return "empty feed or non-2xx response"


def as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := as_text(item))]


def as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


if __name__ == "__main__":
    asyncio.run(main())
