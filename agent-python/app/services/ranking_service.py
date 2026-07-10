from __future__ import annotations

import re
from datetime import datetime, timezone

from app.schemas import NewsItem, RankedNewsItem


IMPACT_TERMS = {
    "earnings": 3.0,
    "revenue": 2.5,
    "guidance": 3.0,
    "profit": 2.0,
    "margin": 1.5,
    "fed": 3.0,
    "inflation": 3.0,
    "rate": 2.0,
    "tariff": 2.5,
    "sanction": 2.5,
    "lawsuit": 2.0,
    "antitrust": 2.5,
    "recall": 2.0,
    "ai": 1.5,
    "chip": 1.5,
    "semiconductor": 2.0,
    "oil": 1.5,
    "gold": 1.5,
}

RISK_TERMS = {
    "probe": 2.0,
    "investigation": 2.0,
    "lawsuit": 2.0,
    "recall": 2.0,
    "default": 3.0,
    "bankruptcy": 3.0,
    "sanction": 2.5,
    "tariff": 2.0,
    "miss": 1.5,
    "cut": 1.5,
}

NOISE_TERMS = {
    "celebrity": -5.0,
    "movie": -5.0,
    "sports": -5.0,
    "coupon": -4.0,
    "recipe": -4.0,
    "gaming discount": -3.0,
}

SOURCE_WEIGHTS = {
    "reuters": 2.0,
    "bloomberg": 2.0,
    "cnbc": 1.5,
    "marketwatch": 1.3,
    "wsj": 1.8,
    "financial times": 1.8,
}


def rank_news(
    items: list[NewsItem],
    query: str = "",
    tickers: list[str] | None = None,
) -> list[RankedNewsItem]:
    """Score news with deterministic, offline-friendly market relevance signals."""

    requested = {ticker.upper() for ticker in tickers or [] if ticker}
    ranked = [_rank_one(item, query=query, requested_tickers=requested) for item in items]
    ranked = [item for item in ranked if item.impact_score > 0]
    ranked.sort(key=lambda item: (item.impact_score, item.confidence), reverse=True)
    return ranked


def _rank_one(item: NewsItem, query: str, requested_tickers: set[str]) -> RankedNewsItem:
    text = f"{item.title} {item.summary}".lower()
    reasons: list[str] = []
    score = 0.0

    symbol = (item.symbol or "").upper()
    if symbol:
        score += 3.0
        reasons.append(f"symbol={symbol}")
    if symbol and symbol in requested_tickers:
        score += 4.0
        reasons.append("requested_symbol_match")

    for token in _query_tokens(query):
        if _contains(text, token):
            score += 1.5
            reasons.append(f"query={token}")

    impact_hits = [term for term in IMPACT_TERMS if _contains(text, term)]
    for term in impact_hits:
        score += IMPACT_TERMS[term]
    if impact_hits:
        reasons.append("impact_terms=" + ",".join(impact_hits[:4]))

    risk_hits = [term for term in RISK_TERMS if _contains(text, term)]
    for term in risk_hits:
        score += RISK_TERMS[term] * 0.7
    if risk_hits:
        reasons.append("risk_terms=" + ",".join(risk_hits[:4]))

    for term, penalty in NOISE_TERMS.items():
        if _contains(text, term):
            score += penalty
            reasons.append(f"noise={term}")

    fresh = _freshness_bonus(item.published_at)
    score += fresh
    reasons.append(f"freshness={fresh:.1f}")

    risk = _risk_level(risk_hits, score)
    confidence = min(0.95, max(0.1, score / 18.0))
    return RankedNewsItem(
        **item.model_dump(),
        impact_score=round(score, 3),
        reason="; ".join(reasons) or "no strong market signal",
        risk=risk,
        confidence=round(confidence, 3),
    )


def _query_tokens(query: str) -> list[str]:
    ignored = {"the", "and", "for", "news", "market", "stock", "stocks", "today"}
    return [
        token
        for token in re.findall(r"[a-zA-Z0-9.]+", query.lower())
        if len(token) >= 3 and token not in ignored
    ]


def _contains(text: str, term: str) -> bool:
    term = term.lower().strip()
    if not term:
        return False
    if len(term) <= 5 and term.replace(".", "").isalnum():
        return re.search(rf"\b{re.escape(term)}\b", text) is not None
    return term in text


def _source_weight(source: str) -> float:
    text = source.lower()
    for name, weight in SOURCE_WEIGHTS.items():
        if name in text:
            return weight
    return 0.4 if source else 0.0


def _freshness_bonus(published_at: str) -> float:
    parsed = _parse_time(published_at)
    if parsed is None:
        return 0.0
    age_hours = (datetime.now(timezone.utc) - parsed).total_seconds() / 3600
    if age_hours < 0:
        return 1.0
    if age_hours <= 24:
        return 2.0
    if age_hours <= 72:
        return 1.0
    if age_hours <= 24 * 7:
        return 0.3
    return -2.0


def _parse_time(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _risk_level(risk_hits: list[str], score: float) -> str:
    if any(term in {"default", "bankruptcy", "sanction"} for term in risk_hits):
        return "high"
    if len(risk_hits) >= 2 or score >= 12:
        return "medium"
    return "low"

