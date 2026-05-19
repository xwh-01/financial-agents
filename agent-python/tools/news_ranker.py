from schemas.news import NewsItem


TICKER_KEYWORDS = {
    "NVDA": ["nvidia", "nvda", "ai chip", "gpu"],
    "TSLA": ["tesla", "tsla", "robotaxi", "ev"],
    "AAPL": ["apple", "aapl", "iphone"],
    "MSFT": ["microsoft", "msft", "azure", "openai"],
    "GOOGL": ["google", "alphabet", "googl", "gemini"],
    "AMZN": ["amazon", "amzn", "aws"],
    "AMD": ["amd", "advanced micro devices"],
    "AVGO": ["broadcom", "avgo"],
    "META": ["meta", "facebook", "instagram"],
}

TOPIC_KEYWORDS = {
    "ai_chips": ["ai chip", "gpu", "semiconductor", "artificial intelligence"],
    "fed_rates": ["fed", "federal reserve", "interest rate", "treasury", "inflation"],
    "gold": ["gold", "precious metal", "safe haven"],
    "oil": ["oil", "crude", "energy", "opec"],
    "earnings": ["earnings", "revenue", "profit", "guidance"],
}

MARKET_TERMS = [
    "stock", "shares", "market", "investors", "earnings",
    "revenue", "guidance", "profit", "loss", "forecast",
    "upgrade", "downgrade", "price target", "fed",
    "inflation", "interest rate", "treasury", "gold", "oil",
]

BAD_TERMS = [
    "sports", "movie", "celebrity", "recipe",
    "travel", "shopping", "game review",
]


def score_news_item(item: NewsItem) -> tuple[float, list[str], list[str], list[str]]:
    text = f"{item.title} {item.content}".lower()

    score = 0.0
    reasons: list[str] = []
    matched_tickers: list[str] = []
    matched_topics: list[str] = []

    for ticker, keywords in TICKER_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            score += 4
            matched_tickers.append(ticker)

    if matched_tickers:
        reasons.append("matched_tickers=" + ",".join(matched_tickers))

    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            score += 2
            matched_topics.append(topic)

    if matched_topics:
        reasons.append("matched_topics=" + ",".join(matched_topics))

    market_hits = [term for term in MARKET_TERMS if term in text]
    if market_hits:
        score += min(4, len(market_hits))
        reasons.append("market_terms=" + ",".join(market_hits[:5]))

    bad_hits = [term for term in BAD_TERMS if term in text]
    if bad_hits:
        score -= 5
        reasons.append("bad_terms=" + ",".join(bad_hits[:3]))

    if len(item.content or "") < 60:
        score -= 1
        reasons.append("content_too_short")

    return score, reasons, matched_tickers, matched_topics


def filter_and_rank_news(
    items: list[NewsItem],
    min_score: float = 5,
) -> list[NewsItem]:
    ranked: list[NewsItem] = []

    for item in items:
        score, reasons, tickers, topics = score_news_item(item)

        if score < min_score:
            continue

        item.relevance_score = score
        item.relevance_reasons = reasons
        item.matched_tickers = tickers
        item.matched_topics = topics

        ranked.append(item)

    ranked.sort(key=lambda item: item.relevance_score, reverse=True)
    return ranked