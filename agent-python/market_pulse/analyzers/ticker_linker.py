from market_pulse.schemas import EntityResult, EventResult, TickerLinks


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


def link_known_entities(entity_result: EntityResult) -> TickerLinks:
    direct: list[str] = []
    related: list[str] = []
    etfs: list[str] = []
    reasons: list[str] = []

    persons = set(entity_result.persons)
    companies = set(entity_result.companies)
    tickers = set(entity_result.tickers)

    if "Elon Musk" in persons or "Tesla" in companies or "TSLA" in tickers:
        direct.append("TSLA")
        related.extend(["ARKK", "QQQ"])
        etfs.extend(["ARKK", "QQQ"])
        reasons.append("识别到 Elon Musk / Tesla / TSLA，关联 Tesla 及成长科技 ETF。")

    if "Jensen Huang" in persons or "Nvidia" in companies or "NVDA" in tickers:
        direct.append("NVDA")
        related.extend(["AMD", "TSM", "SMH", "QQQ"])
        etfs.extend(["SMH", "QQQ"])
        reasons.append("识别到 Jensen Huang / Nvidia / NVDA，关联半导体产业链。")

    if "Sam Altman" in persons or "OpenAI" in companies or "Microsoft" in companies:
        direct.append("MSFT")
        related.extend(["NVDA", "GOOG", "QQQ"])
        etfs.extend(["QQQ"])
        reasons.append(
            "识别到 Sam Altman / OpenAI / Microsoft，关联 AI 基础设施与云计算。"
        )

    return TickerLinks(
        direct_tickers=_dedupe(direct),
        related_tickers=_dedupe(related),
        etfs=_dedupe(etfs),
        reason="；".join(reasons) if reasons else "未能关联到明确股票或 ETF。",
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
