from schemas.entity import EntityResult
from schemas.event import EventResult
from schemas.ticker import TickerLinks
from tools.entity_lookup import link_known_entities


def link_tickers(
    entity_result: EntityResult,
    event_result: EventResult,
) -> TickerLinks:
    ticker_links = link_known_entities(entity_result)

    confidence = ticker_links.confidence

    if event_result.event_type == "unknown":
        confidence = max(0.2, confidence - 0.1)

    return TickerLinks(
        direct_tickers=ticker_links.direct_tickers,
        related_tickers=ticker_links.related_tickers,
        etfs=ticker_links.etfs,
        reason=ticker_links.reason,
        confidence=confidence,
    )