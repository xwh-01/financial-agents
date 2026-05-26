import re
from urllib.parse import urlparse

SOURCE_WEIGHTS = {
    "reuters": 1.0,
    "bloomberg": 1.0,
    "cnbc": 0.9,
    "yahoo finance": 0.85,
    "marketwatch": 0.8,
    "google news": 0.75,
}

DOMAIN_WEIGHTS = {
    "reuters.com": 1.0,
    "bloomberg.com": 1.0,
    "cnbc.com": 0.9,
    "finance.yahoo.com": 0.85,
    "marketwatch.com": 0.8,
    "news.google.com": 0.75,
}

IR_NEWSROOM_KEYWORDS = re.compile(
    r"investor|ir\b|press|newsroom|corporate|media\b",
    re.IGNORECASE,
)


def get_source_weight(source_name: str | None, url: str | None = None) -> float:
    name = (source_name or "").strip()
    url_str = (url or "").strip()

    if name:
        lower = name.lower()
        for key, weight in SOURCE_WEIGHTS.items():
            if key in lower:
                return weight

    if url_str:
        parsed = urlparse(url_str if "://" in url_str else f"https://{url_str}")
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]

        for domain_key, weight in DOMAIN_WEIGHTS.items():
            if domain_key in host:
                return weight

    if name and IR_NEWSROOM_KEYWORDS.search(name):
        return 0.95

    if url_str and IR_NEWSROOM_KEYWORDS.search(url_str):
        return 0.95

    return 0.5
