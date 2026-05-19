from schemas.news import NewsItem
from tools.news_search import search_news
import math


DEFAULT_MARKET_QUERIES = [
    # 泛市场：今天市场整体发生了什么
    "stock market today major news",
    "global financial markets today",
    "market movers today stocks",
    "stocks moving on news today",

    # 宏观：利率、通胀、美元、就业、国债
    "Federal Reserve interest rates market impact",
    "inflation data stock market impact",
    "US treasury yields dollar stock market",
    "jobs report unemployment stock market",

    # 大宗商品：黄金、原油、能源
    "gold price market impact",
    "oil price energy market impact",
    "commodity prices inflation market impact",

    # 地缘政治 / 政策 / 监管
    "geopolitical risk stock market impact",
    "government regulation stock market impact",
    "tariffs trade war market impact",

    # 行业轮动
    "bank stocks market news",
    "energy stocks market news",
    "healthcare stocks market news",
    "retail consumer stocks market news",
    "semiconductor stocks market news",
    "real estate stocks interest rates",
]

async def collect_latest_market_news(
    limit: int = 80,
    language: str = "en",
    translate_to_zh: bool = True,
) -> list[NewsItem]:
    """
    Build a candidate news pool from multiple finance-related queries.

    limit means candidate pool size, not final analysis size.
    """
    per_query_limit = max(5, math.ceil(limit / len(DEFAULT_MARKET_QUERIES)))
    all_items: list[NewsItem] = []

    for query in DEFAULT_MARKET_QUERIES:
        try:
            items = await search_news(
                query=query,
                limit=per_query_limit,
                language=language,
                translate_to_zh=translate_to_zh,
            )
            all_items.extend(items)
        except Exception:
            continue

    return _dedupe_news(all_items)


def _dedupe_news(items: list[NewsItem]) -> list[NewsItem]:
    seen_urls = set()
    seen_titles = set()
    result: list[NewsItem] = []

    for item in items:
        url_key = (item.url or "").strip().lower()
        title_key = (item.title or "").strip().lower()

        if url_key and url_key in seen_urls:
            continue

        if title_key and title_key in seen_titles:
            continue

        if url_key:
            seen_urls.add(url_key)

        if title_key:
            seen_titles.add(title_key)

        result.append(item)

    return result
