COMPANY_TICKER_ALIASES: dict[str, str] = {
    "3m": "MMM",
    "abbott": "ABT",
    "abbott laboratories": "ABT",
    "abbvie": "ABBV",
    "adobe": "ADBE",
    "advanced micro devices": "AMD",
    "airbnb": "ABNB",
    "alibaba": "BABA",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "amazon web services": "AMZN",
    "amd": "AMD",
    "american express": "AXP",
    "amgen": "AMGN",
    "apple": "AAPL",
    "applied materials": "AMAT",
    "arm": "ARM",
    "arm holdings": "ARM",
    "astrazeneca": "AZN",
    "atlassian": "TEAM",
    "baidu": "BIDU",
    "bank of america": "BAC",
    "berkshire hathaway": "BRK.B",
    "blackrock": "BLK",
    "blackstone": "BX",
    "boeing": "BA",
    "booking": "BKNG",
    "booking holdings": "BKNG",
    "broadcom": "AVGO",
    "byd": "BYDDY",
    "caterpillar": "CAT",
    "charles schwab": "SCHW",
    "chevron": "CVX",
    "chipotle": "CMG",
    "cisco": "CSCO",
    "citigroup": "C",
    "cloudflare": "NET",
    "coca-cola": "KO",
    "coinbase": "COIN",
    "conocophillips": "COP",
    "costco": "COST",
    "crowdstrike": "CRWD",
    "datadog": "DDOG",
    "deere": "DE",
    "disney": "DIS",
    "duke energy": "DUK",
    "eli lilly": "LLY",
    "estee lauder": "EL",
    "exxon": "XOM",
    "exxon mobil": "XOM",
    "ford": "F",
    "freeport-mcmoran": "FCX",
    "general electric": "GE",
    "general motors": "GM",
    "gilead": "GILD",
    "gilead sciences": "GILD",
    "goldman sachs": "GS",
    "google": "GOOGL",
    "home depot": "HD",
    "honeywell": "HON",
    "ibm": "IBM",
    "intel": "INTC",
    "intuit": "INTU",
    "intuitive surgical": "ISRG",
    "jd.com": "JD",
    "johnson & johnson": "JNJ",
    "johnson and johnson": "JNJ",
    "jpmorgan": "JPM",
    "jpmorgan chase": "JPM",
    "kla": "KLAC",
    "lam research": "LRCX",
    "li auto": "LI",
    "linde": "LIN",
    "lockheed martin": "LMT",
    "lowe's": "LOW",
    "lululemon": "LULU",
    "mastercard": "MA",
    "mcdonald's": "MCD",
    "meta": "META",
    "micron": "MU",
    "microsoft": "MSFT",
    "moderna": "MRNA",
    "mongodb": "MDB",
    "morgan stanley": "MS",
    "netflix": "NFLX",
    "netease": "NTES",
    "newmont": "NEM",
    "nextera energy": "NEE",
    "nio": "NIO",
    "nike": "NKE",
    "northrop grumman": "NOC",
    "novo nordisk": "NVO",
    "nvidia": "NVDA",
    "occidental petroleum": "OXY",
    "oracle": "ORCL",
    "palantir": "PLTR",
    "palo alto networks": "PANW",
    "paypal": "PYPL",
    "pdd": "PDD",
    "pdd holdings": "PDD",
    "pepsico": "PEP",
    "pfizer": "PFE",
    "procter & gamble": "PG",
    "qualcomm": "QCOM",
    "regeneron": "REGN",
    "rivian": "RIVN",
    "rtx": "RTX",
    "salesforce": "CRM",
    "sap": "SAP",
    "schlumberger": "SLB",
    "servicenow": "NOW",
    "shopify": "SHOP",
    "snowflake": "SNOW",
    "sofi": "SOFI",
    "starbucks": "SBUX",
    "taiwan semiconductor": "TSM",
    "target": "TGT",
    "tencent": "TCEHY",
    "tesla": "TSLA",
    "texas instruments": "TXN",
    "thermo fisher": "TMO",
    "tsmc": "TSM",
    "uber": "UBER",
    "unitedhealth": "UNH",
    "unitedhealth group": "UNH",
    "visa": "V",
    "walmart": "WMT",
    "wells fargo": "WFC",
    "xpeng": "XPEV",
    "zscaler": "ZS",
}


TOPIC_ETF_ALIASES: dict[str, list[str]] = {
    "ai": ["QQQ", "SMH"],
    "artificial intelligence": ["QQQ", "SMH"],
    "bank": ["XLF"],
    "banks": ["XLF"],
    "biotech": ["XLV"],
    "cloud": ["QQQ"],
    "energy": ["XLE"],
    "gold": ["GLD"],
    "healthcare": ["XLV"],
    "oil": ["XLE", "USO"],
    "semiconductor": ["SMH", "SOXX"],
    "software": ["QQQ"],
    "treasury": ["TLT"],
}


def map_companies_to_tickers(companies: list[str]) -> list[str]:
    result: list[str] = []
    for company in companies:
        key = _normalize_alias(company)
        ticker = COMPANY_TICKER_ALIASES.get(key)
        if ticker:
            result.append(ticker)
    return _dedupe(result)


def map_topics_to_etfs(topics: list[str]) -> list[str]:
    result: list[str] = []
    for topic in topics:
        key = _normalize_alias(topic)
        for alias, etfs in TOPIC_ETF_ALIASES.items():
            if alias in key:
                result.extend(etfs)
    return _dedupe(result)


def _normalize_alias(value: str) -> str:
    return " ".join(str(value or "").strip().lower().replace(",", " ").split())


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = item.strip().upper()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
