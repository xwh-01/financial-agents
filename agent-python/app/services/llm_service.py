from __future__ import annotations

from app.config import settings
from app.schemas import MarketSignal, RankedNewsItem


class LLMService:
    """Central LLM gateway. Falls back to deterministic analysis without an API key."""

    def __init__(self) -> None:
        self.last_model: str | None = None
        self.last_token_usage: dict | None = None

    async def analyze_impact(self, item: RankedNewsItem) -> MarketSignal:
        if not settings.llm_api_key:
            self.last_model = "offline-heuristic"
            self.last_token_usage = None
            return _heuristic_signal(item)

        try:
            from clients.llm_client import chat_completion

            self.last_model = settings.llm_model
            self.last_token_usage = None
            content = await chat_completion(
                "You are a cautious market intelligence analyst.",
                (
                    "Return a concise market observation, not investment advice. "
                    "Explain impact, risk, and confidence.\n\n"
                    f"Title: {item.title}\nSummary: {item.summary}\nSymbol: {item.symbol}\n"
                    f"Ranking reason: {item.reason}"
                ),
            )
            signal = _heuristic_signal(item)
            signal.summary = content[:600]
            return signal
        except Exception:
            self.last_model = "offline-heuristic"
            self.last_token_usage = None
            return _heuristic_signal(item)


def _heuristic_signal(item: RankedNewsItem) -> MarketSignal:
    summary = item.summary or item.title
    return MarketSignal(
        title=item.title,
        summary=summary[:300],
        url=item.url,
        source=item.source,
        published_at=item.published_at,
        symbol=item.symbol,
        impact_score=item.impact_score,
        reason=item.reason,
        risk=item.risk,
        confidence=item.confidence,
    )
