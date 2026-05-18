from schemas.entity import EntityResult
from schemas.ticker import TickerLinks


def link_known_entities(entity_result: EntityResult) -> TickerLinks:
    """
    第一版不使用 mock 文件。
    这里使用内置确定性规则。
    后续可以改成数据库或真实公司实体服务。
    """
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
        reasons.append("识别到 Sam Altman / OpenAI / Microsoft，关联 AI 基础设施与云计算。")

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