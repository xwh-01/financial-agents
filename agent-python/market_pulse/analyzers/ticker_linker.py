from market_pulse.schemas import EntityResult, EventResult, TickerLinks
from market_pulse.analyzers.ticker_catalog import (
    get_sector_peers,
    map_companies_to_tickers,
    map_topics_to_etfs,
)


def link_tickers(
    entity_result: EntityResult,
    event_result: EventResult,
) -> TickerLinks:
    """
    Map resolved entities to market instruments (tickers, related peers, ETFs).

    Steps:
      1. Use entity_result.tickers directly as direct tickers
      2. Map company names -> tickers via ticker_catalog
      3. Map topics -> ETFs via ticker_catalog
      4. For each direct ticker, find sector peers and ETFs

    If the event_type is "unknown", confidence is slightly reduced since the
    ticker mapping may be less relevant.
    """
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


def link_known_entities(entity_result: EntityResult) -> TickerLinks:
    direct: list[str] = []
    related: list[str] = []
    etfs: list[str] = []
    reasons: list[str] = []

    tickers = set(entity_result.tickers)

    for ticker in sorted(tickers):
        direct.append(ticker)

    mapped_companies = map_companies_to_tickers(entity_result.companies)
    if mapped_companies:
        direct.extend(mapped_companies)
        reasons.append("根据公司名称映射到股票代码：" + ", ".join(mapped_companies))

    mapped_etfs = map_topics_to_etfs(entity_result.topics)
    if mapped_etfs:
        etfs.extend(mapped_etfs)
        related.extend(mapped_etfs)
        reasons.append("根据行业主题关联到 ETF：" + ", ".join(mapped_etfs))

    all_direct = list(set(direct))
    for ticker in all_direct:
        peer_related, peer_etfs = get_sector_peers(ticker)
        if peer_related:
            related.extend(peer_related)
        if peer_etfs:
            etfs.extend(peer_etfs)
            related.extend(peer_etfs)
        if peer_related or peer_etfs:
            peers = peer_related + peer_etfs
            if peers:
                reasons.append(f"{ticker} 所属板块关联：{', '.join(peers[:6])}")

    return TickerLinks(
        direct_tickers=_dedupe(direct),
        related_tickers=_dedupe(related),
        etfs=_dedupe(etfs),
        reason="；".join(reasons) if reasons else _generic_reason(direct),
        confidence=0.85 if direct else 0.2,
    )


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _generic_reason(direct: list[str]) -> str:
    if direct:
        return "根据新闻实体识别结果关联到股票代码：" + ", ".join(_dedupe(direct))
    return "未能关联到明确股票或 ETF。"
