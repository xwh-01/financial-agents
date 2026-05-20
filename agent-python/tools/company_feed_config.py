import json
from pathlib import Path
from typing import TypedDict

from app.config import settings


class CompanyFeedConfig(TypedDict):
    company: str
    ticker: str
    rss_feeds: list[str]
    search_queries: list[str]


def load_company_feeds() -> list[CompanyFeedConfig]:
    path = _config_path()

    if not path.exists():
        print(f"[company-feeds] config not found: {path}")
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            print(f"[company-feeds] invalid config root, expected list: {path}")
            return []

        configs: list[CompanyFeedConfig] = []
        for item in raw:
            if not isinstance(item, dict):
                continue

            company = _as_text(item.get("company"))
            ticker = _as_text(item.get("ticker")).upper()
            if not company or not ticker:
                continue

            configs.append(
                {
                    "company": company,
                    "ticker": ticker,
                    "rss_feeds": _as_str_list(item.get("rss_feeds")),
                    "search_queries": _as_str_list(item.get("search_queries")),
                }
            )

        return configs

    except Exception as exc:
        print(f"[company-feeds] failed to load {path}: {exc}")
        return []


def _config_path() -> Path:
    configured = Path(settings.company_feeds_path)
    if configured.is_absolute():
        return configured

    return Path(__file__).resolve().parents[1] / configured


def _as_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_str_list(value) -> list[str]:
    if not isinstance(value, list):
        return []

    result: list[str] = []
    for item in value:
        text = _as_text(item)
        if text:
            result.append(text)

    return result
