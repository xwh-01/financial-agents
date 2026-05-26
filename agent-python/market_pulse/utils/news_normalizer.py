import hashlib
import re
from urllib.parse import parse_qs, urlparse, urlunparse

TRACKING_PARAMS = frozenset({
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "fbclid",
    "gclid",
    "gclsrc",
    "dclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "_ga",
    "ref",
    "referrer",
    "source",
    "trk",
})


def normalize_title(title: str) -> str:
    text = title.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9 ]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_url(url: str) -> str:
    text = url.strip().lower()
    if not text:
        return ""

    parsed = urlparse(text)
    query = parse_qs(parsed.query, keep_blank_values=True)
    clean_query_pairs: list[tuple[str, str]] = []
    for key, values in query.items():
        if key.lower() not in TRACKING_PARAMS:
            for value in values:
                clean_query_pairs.append((key, value))

    clean_query = "&".join(f"{k}={v}" for k, v in clean_query_pairs)
    clean = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        clean_query,
        "",  # fragment stripped
    ))
    return clean


def make_content_hash(title: str, url: str | None = None) -> str:
    norm_title = normalize_title(title)
    norm_url = normalize_url(url or "")
    raw = f"{norm_title}|{norm_url}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
