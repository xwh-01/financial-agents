import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from market_pulse.rankers.source_weight import get_source_weight
from market_pulse.schemas import NewsItem


MAX_NEWS_AGE_DAYS = 7


TICKER_KEYWORDS = {
    "NVDA": ["nvidia", "nvda", "ai chip", "gpu"],
    "TSLA": ["tesla", "tsla", "robotaxi"],
    "AAPL": ["apple", "aapl", "iphone"],
    "MSFT": ["microsoft", "msft", "azure", "openai"],
    "GOOGL": ["google", "alphabet", "googl", "gemini"],
    "AMZN": ["amazon", "amzn", "amazon web services"],
    "AMD": ["amd", "advanced micro devices"],
    "AVGO": ["broadcom", "avgo"],
    "META": ["meta", "facebook", "instagram"],
}

EVENT_KEYWORDS = {
    "macro": [
        "fed",
        "federal reserve",
        "interest rate",
        "inflation",
        "cpi",
        "jobs report",
        "unemployment",
        "treasury yields",
        "dollar",
    ],
    "geopolitical": [
        "war",
        "conflict",
        "sanctions",
        "tariffs",
        "trade war",
        "geopolitical",
    ],
    "commodities": [
        "gold",
        "oil",
        "crude",
        "natural gas",
        "commodity",
        "opec",
    ],
    "policy": [
        "regulation",
        "antitrust",
        "government",
        "ban",
        "subsidy",
        "tax",
    ],
    "sector_rotation": [
        "bank stocks",
        "energy stocks",
        "healthcare stocks",
        "retail stocks",
        "real estate stocks",
    ],
    "earnings": [
        "earnings",
        "revenue",
        "guidance",
        "profit",
        "margin",
    ],
}

TOPIC_KEYWORDS = {
    "ai_chips": ["ai chip", "gpu", "semiconductor", "artificial intelligence"],
    "fed_rates": ["fed", "federal reserve", "interest rate", "treasury", "inflation"],
    "gold": ["gold", "precious metal", "safe haven"],
    "oil": ["oil", "crude", "energy", "opec"],
    "earnings": ["earnings", "revenue", "profit", "guidance"],
}

MARKET_TERMS = [
    "stock",
    "shares",
    "market",
    "investors",
    "earnings",
    "revenue",
    "guidance",
    "profit",
    "loss",
    "forecast",
    "upgrade",
    "downgrade",
    "price target",
    "fed",
    "inflation",
    "interest rate",
    "treasury",
    "gold",
    "oil",
]

BAD_TERMS = [
    "sports",
    "movie",
    "celebrity",
    "recipe",
    "travel",
    "shopping",
    "game review",
]


def contains_keyword(text: str, keyword: str) -> bool:
    keyword = keyword.strip().lower()

    if not keyword:
        return False

    # 短 ticker / 短词必须完整单词匹配，避免 ev、aws、amd 乱命中
    if len(keyword) <= 5 and keyword.replace(".", "").isalpha():
        return re.search(rf"\b{re.escape(keyword)}\b", text, re.IGNORECASE) is not None

    return keyword in text.lower()


def score_news_item(
    item: NewsItem,
) -> tuple[float, list[str], list[str], list[str], list[str]]:
    text = f"{item.title} {item.content}".lower()

    score = 0.0
    reasons: list[str] = []
    matched_tickers: list[str] = []
    matched_topics: list[str] = []
    matched_events: list[str] = []

    for event_type, keywords in EVENT_KEYWORDS.items():
        if any(contains_keyword(text, keyword) for keyword in keywords):
            score += 3
            matched_events.append(event_type)

    if matched_events:
        reasons.append("matched_events=" + ",".join(matched_events))

    for ticker, keywords in TICKER_KEYWORDS.items():
        if any(contains_keyword(text, keyword) for keyword in keywords):
            score += 4
            matched_tickers.append(ticker)

    if matched_tickers:
        reasons.append("matched_tickers=" + ",".join(matched_tickers))

    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(contains_keyword(text, keyword) for keyword in keywords):
            score += 2
            matched_topics.append(topic)

    if matched_topics:
        reasons.append("matched_topics=" + ",".join(matched_topics))

    market_hits = [term for term in MARKET_TERMS if contains_keyword(text, term)]
    if market_hits:
        score += min(4, len(market_hits))
        reasons.append("market_terms=" + ",".join(market_hits[:5]))

    bad_hits = [term for term in BAD_TERMS if contains_keyword(text, term)]
    if bad_hits:
        score -= 5
        reasons.append("bad_terms=" + ",".join(bad_hits[:3]))

    if len(item.content or "") < 60:
        score -= 1
        reasons.append("content_too_short")

    return score, reasons, matched_tickers, matched_topics, matched_events


def filter_and_rank_news(
    items: list[NewsItem],
    min_score: float = 3,
    query: str = "",
) -> list[NewsItem]:
    ranked: list[NewsItem] = []
    query_matched: list[NewsItem] = []

    for item in items:
        score, reasons, tickers, topics, events = score_news_item(item)
        fresh_score = freshness_score(item)
        fresh_reason = _freshness_reason(item)
        score += fresh_score
        reasons.append(f"freshness={fresh_reason}")

        sw = get_source_weight(item.source, item.url)
        item.source_weight = sw
        item.freshness_score = fresh_score
        score += sw * 5
        reasons.append(f"source_weight={sw:.2f}")

        if parse_news_time(item.published_at) and not is_recent_news(
            item,
            max_age_days=MAX_NEWS_AGE_DAYS,
        ):
            item.relevance_score = score
            item.relevance_reasons = reasons
            item.matched_tickers = tickers
            item.matched_topics = topics
            item.matched_events = events
            continue

        query_hits = _query_hits(f"{item.title} {item.content}", query)
        if query_hits:
            score += min(16, len(query_hits) * 4)
            reasons.append("matched_query=" + ",".join(query_hits[:5]))

        item.relevance_score = score
        item.relevance_reasons = reasons
        item.matched_tickers = tickers
        item.matched_topics = topics
        item.matched_events = events

        if score < min_score:
            continue

        ranked.append(item)
        if query_hits:
            query_matched.append(item)

    if query.strip() and query_matched:
        ranked = query_matched

    ranked.sort(key=lambda item: item.relevance_score, reverse=True)
    return ranked


def parse_news_time(published_at: str) -> datetime | None:
    text = (published_at or "").strip()
    if not text:
        return None

    normalized = text
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        value = datetime.fromisoformat(normalized)
        return _ensure_aware_utc(value)
    except ValueError:
        pass

    try:
        value = parsedate_to_datetime(text)
        return _ensure_aware_utc(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        pass

    known_formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
    )
    for fmt in known_formats:
        try:
            value = datetime.strptime(text, fmt)
            return _ensure_aware_utc(value)
        except ValueError:
            continue

    return None


def is_recent_news(item: NewsItem, max_age_days: int = 7) -> bool:
    published_at = parse_news_time(item.published_at)
    if published_at is None:
        return True

    age_seconds = (_utc_now() - published_at).total_seconds()
    return age_seconds <= max_age_days * 24 * 60 * 60


def freshness_score(item: NewsItem) -> float:
    published_at = parse_news_time(item.published_at)
    if published_at is None:
        return -1.5

    age_seconds = (_utc_now() - published_at).total_seconds()
    if age_seconds < 0:
        return 3.0

    hours = age_seconds / 3600
    if hours <= 6:
        return 3.0
    if hours <= 24:
        return 2.0
    if hours <= 72:
        return 1.0
    if hours <= MAX_NEWS_AGE_DAYS * 24:
        return 0.25
    return -10.0


def _query_hits(text: str, query: str) -> list[str]:
    query = query.strip().lower()
    if not query:
        return []

    text = text.lower()
    hits: list[str] = []
    if query in text:
        hits.append(query)

    tokens = re.findall(r"[a-zA-Z0-9.]+", query)
    ignored = {
        "and",
        "or",
        "the",
        "for",
        "with",
        "news",
        "today",
        "market",
        "markets",
        "stock",
        "stocks",
    }
    for token in tokens:
        if len(token) < 3 or token in ignored:
            continue
        if contains_keyword(text, token) and token not in hits:
            hits.append(token)

    return hits


def _freshness_reason(item: NewsItem) -> str:
    published_at = parse_news_time(item.published_at)
    if published_at is None:
        return "missing_published_at"

    age_seconds = (_utc_now() - published_at).total_seconds()
    if age_seconds < 0:
        return "within_6h"

    hours = age_seconds / 3600
    if hours <= 6:
        return "within_6h"
    if hours <= 24:
        return "within_24h"
    if hours <= 72:
        return "within_3d"
    if hours <= MAX_NEWS_AGE_DAYS * 24:
        return "within_7d"
    return "too_old"


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
