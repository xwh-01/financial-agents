from datetime import datetime, timezone

from market_pulse.rankers.source_weight import get_source_weight
from market_pulse.schemas import NewsItem
from market_pulse.utils.news_normalizer import make_content_hash, normalize_title, normalize_url


def dedupe_news(news_items: list[NewsItem]) -> list[NewsItem]:
    """
    Remove duplicate news items by URL, title, and content hash.

    Three-level deduplication:
      1. Normalized URL (stripped tracking params: utm_*, fbclid, gclid, etc.)
      2. Normalized title (lowercased, whitespace-collapsed, non-alphanumeric stripped)
      3. Content hash (SHA256 of normalized title + URL)

    When a duplicate is detected, the item with the higher source weight wins.
    Ties break by recency (newer published_at).
    """
    seen_urls: dict[str, int] = {}
    seen_titles: dict[str, int] = {}
    seen_hashes: dict[str, int] = {}
    keep: dict[int, int] = {}  # orig_index -> orig_index

    for idx, item in enumerate(news_items):
        norm_url = normalize_url(item.url)
        norm_title = normalize_title(item.title)
        content_hash = make_content_hash(item.title, item.url)

        conflict_idx: int | None = None
        for key, store in (
            (norm_url, seen_urls),
            (norm_title, seen_titles),
            (content_hash, seen_hashes),
        ):
            if key and key in store:
                existing_idx = store[key]
                if conflict_idx is None:
                    conflict_idx = existing_idx
                elif store[key] != conflict_idx:
                    continue

        if conflict_idx is not None:
            resolved = _resolve_duplicate(news_items, conflict_idx, idx)
            if resolved != idx:
                continue
            # New item wins — swap keep entries and update dedup stores.
            keep.pop(conflict_idx, None)
            keep[idx] = idx
            for key, store in (
                (norm_url, seen_urls),
                (norm_title, seen_titles),
                (content_hash, seen_hashes),
            ):
                if key:
                    store[key] = resolved
        else:
            for key, store in (
                (norm_url, seen_urls),
                (norm_title, seen_titles),
                (content_hash, seen_hashes),
            ):
                if key:
                    store[key] = idx
            keep[idx] = idx

    result: list[NewsItem] = []
    for orig_idx in sorted(keep.values()):
        result.append(news_items[orig_idx])
    return result


def _resolve_duplicate(
    items: list[NewsItem],
    idx_a: int,
    idx_b: int,
) -> int:
    a = items[idx_a]
    b = items[idx_b]
    wa = get_source_weight(a.source or "", a.url)
    wb = get_source_weight(b.source or "", b.url)
    if wa > wb:
        return idx_a
    if wb > wa:
        return idx_b

    ta = _parse_time(a.published_at)
    tb = _parse_time(b.published_at)
    if ta and tb:
        return idx_a if ta >= tb else idx_b
    if ta:
        return idx_a
    if tb:
        return idx_b
    return idx_a


def filter_fresh_news(
    news_items: list[NewsItem],
    max_age_hours: int = 72,
) -> list[NewsItem]:
    """
    Keep only items within max_age_hours of the current time.

    Items with unparseable timestamps are kept (assumed fresh), while items
    older than the threshold are dropped. This is a simple recency gate,
    separate from the more nuanced freshness scoring used in ranking.
    """
    now = datetime.now(timezone.utc)
    result: list[NewsItem] = []
    for item in news_items:
        published_at = _parse_time(item.published_at)
        if published_at is None:
            result.append(item)
            continue
        age_hours = (now - published_at).total_seconds() / 3600
        if age_hours <= max_age_hours:
            result.append(item)
    return result


def _parse_time(published_at: str) -> datetime | None:
    text = (published_at or "").strip()
    if not text:
        return None

    normalized = text
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass

    known_formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    )
    for fmt in known_formats:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None
