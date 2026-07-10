"""Layer 1: query-driven coarse filter. Fast regex matching to reduce ~300→30.

Each user intent (ticker/topic row) gets guaranteed recall slots so multi-target
watchlists don't collapse into a single dominant theme.
"""

import re
from datetime import datetime, timezone

from market_pulse.rankers.news_ranker import (
    _item_text,
    _news_key,
    _dedupe_lower,
    is_recent_news,
    parse_news_time,
)
from market_pulse.rankers.source_weight import get_source_weight
from market_pulse.schemas import NewsItem

COARSE_LIMIT = 30
INTENT_PER_SLOT = 5
STOP_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "by", "for", "from",
    "how", "in", "into", "is", "it", "market", "news", "of",
    "on", "or", "pulse", "the", "to", "watchlist", "what", "with",
})


def coarse_filter(
    items: list[NewsItem],
    query: str,
    limit: int = COARSE_LIMIT,
) -> list[NewsItem]:
    """
    Layer 1 coarse filter — fast regex matching to reduce ~300 candidates to ~30.

    Strategy:
      1. Hard filter + dedup (remove empty titles, stale items, short content, duplicates)
      2. Parse watchlist query into intent groups (ticker rows, topic rows, etc.)
      3. Guarantee per-intent recall: each intent gets up to INTENT_PER_SLOT slots
         so a multi-ticker watchlist doesn't collapse to a single dominant theme
      4. Fill remaining slots with global-scored items sorted by relevance
    """
    deduped = _hard_filter_and_dedupe(items)
    if not deduped:
        return []

    intents = _parse_intents(query)
    if not intents:
        return _fallback_sort(deduped)[:limit]

    all_terms = _dedupe_lower([t for intent in intents for t in intent["terms"]])
    scored = _score_items(deduped, all_terms)
    scored.sort(key=lambda x: x[1], reverse=True)

    recalled_keys: set[str] = set()
    per_intent = max(2, INTENT_PER_SLOT)
    for intent in intents:
        intent_terms = intent["terms"]
        intent_scored = _score_items(deduped, intent_terms)
        intent_scored = [(item, s) for item, s in intent_scored if s > 0]
        intent_scored.sort(key=lambda x: x[1], reverse=True)
        for item, _ in intent_scored[:per_intent]:
            recalled_keys.add(_news_key(item))

    result: list[NewsItem] = []
    for item, _ in scored:
        if item_key(item) in recalled_keys and item_key(item) not in _seen(result):
            result.append(item)

    for item, _ in scored:
        if len(result) >= limit:
            break
        if item_key(item) not in _seen(result):
            result.append(item)

    return result[:limit]


def _parse_intents(query: str) -> list[dict]:
    text = (query or "").strip()
    if not text:
        return []

    intents: list[dict] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith("market pulse for watchlist"):
            continue
        match = re.match(r"^([A-Za-z_ ]{2,30}):\s*(.+)$", line)
        if match:
            kind = match.group(1).strip().lower().replace(" ", "_")
            value = match.group(2).strip()
            for part in re.split(r"[,;/|]", value):
                part = part.strip()
                if part:
                    terms = _tokenize_phrase(part)
                    if terms:
                        intents.append({"kind": kind, "text": part, "terms": terms})
        else:
            terms = _tokenize_phrase(line)
            if terms:
                intents.append({"kind": "query", "text": line, "terms": terms})

    if not intents and text:
        terms = _tokenize_phrase(text)
        if terms:
            intents = [{"kind": "query", "text": text, "terms": terms}]

    if not intents:
        intents = [{"kind": "market", "text": "market", "terms": ["market"]}]

    return intents


def _tokenize_phrase(phrase: str) -> list[str]:
    tokens: list[str] = []
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9&.+-]*", phrase.lower()):
        if len(token) >= 2 and token not in STOP_WORDS and token != "market":
            tokens.append(token)
    if not tokens and len(phrase.strip()) >= 2:
        tokens = [phrase.strip().lower()]
    return _dedupe_lower(tokens)


def _score_items(items: list[NewsItem], query_terms: list[str]) -> list[tuple[NewsItem, float]]:
    if not query_terms:
        return [(item, 0.0) for item in items]

    scored: list[tuple[NewsItem, float]] = []
    for item in items:
        scored.append((item, _query_relevance_score(item, query_terms)))
    return scored


def _query_relevance_score(item: NewsItem, query_terms: list[str]) -> float:
    text = _item_text(item).lower()

    hits = 0
    for term in query_terms:
        if len(term) <= 2:
            if re.search(rf"\b{re.escape(term)}\b", text):
                hits += 1
        elif term in text:
            hits += 1

    coverage = hits / max(len(query_terms), 1)
    score = coverage * 10.0

    source = get_source_weight(item.source, item.url)
    score += source * 0.5

    published = parse_news_time(item.published_at)
    if published:
        hours = (datetime.now(timezone.utc) - published).total_seconds() / 3600
        if hours <= 6:
            score += 1.0
        elif hours <= 24:
            score += 0.5

    title_lower = (item.title or "").lower()
    title_hits = sum(1 for t in query_terms if t in title_lower)
    score += title_hits * 0.5

    return score


def _hard_filter_and_dedupe(items: list[NewsItem]) -> list[NewsItem]:
    seen: set[str] = set()
    result: list[NewsItem] = []
    for item in items:
        title = (item.title or "").strip()
        if not title:
            continue
        if not is_recent_news(item):
            continue
        text = _item_text(item)
        if len(text) < 20:
            continue
        key = _news_key(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _fallback_sort(items: list[NewsItem]) -> list[NewsItem]:
    return sorted(
        items,
        key=lambda item: (
            parse_news_time(item.published_at) or datetime.min.replace(tzinfo=timezone.utc),
            get_source_weight(item.source, item.url),
        ),
        reverse=True,
    )


def item_key(item: NewsItem) -> str:
    return _news_key(item)


def _seen(items: list[NewsItem]) -> set[str]:
    return {item_key(item) for item in items}
