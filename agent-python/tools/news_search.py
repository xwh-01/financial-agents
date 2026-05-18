import httpx

from app.config import settings
from tools.translator import translate_to_chinese
from app.errors import ExternalServiceNotConfigured, ExternalServiceError
from schemas.news import NewsItem


async def search_news(
    query: str = "",
    limit: int = 5,
    language: str = "en",
    translate_to_zh: bool = True,
) -> list[NewsItem]:
    """
    使用 Marketaux /v1/news/all 搜索金融新闻。

    .env:
    NEWS_BASE_URL=https://api.marketaux.com/v1/news/all
    NEWS_API_KEY=your_marketaux_api_token

    Marketaux 使用 api_token 作为认证参数。
    """

    if not settings.news_api_key:
        raise ExternalServiceNotConfigured("NEWS_API_KEY is not configured.")

    if not settings.news_base_url:
        raise ExternalServiceNotConfigured("NEWS_BASE_URL is not configured.")

    params = {
        "api_token": settings.news_api_key,
        "limit": max(1, min(limit, 20)),
        "language": language,
    }
    if query.strip():
        params["search"] = query.strip()

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(settings.news_base_url, params=params)

        if resp.status_code >= 400:
            raise ExternalServiceError(
                f"Marketaux news request failed: status={resp.status_code}, body={resp.text}"
            )

        data = resp.json()

        if "error" in data:
            raise ExternalServiceError(f"Marketaux error: {data}")

        articles = data.get("data", [])
        items: list[NewsItem] = []

        for idx, article in enumerate(articles):
            title = article.get("title") or ""
            description = article.get("description") or ""
            snippet = article.get("snippet") or ""
            url = article.get("url") or ""
            published_at = article.get("published_at") or ""
            source = article.get("source") or ""

            content = description or snippet

            if not title and not content:
                continue

            title_zh = ""
            content_zh = ""

            if translate_to_zh:
                try:
                    title_zh = await translate_to_chinese(title)
                except Exception:
                    title_zh = ""

                try:
                    content_zh = await translate_to_chinese(content)
                except Exception:
                    content_zh = ""

            items.append(
                NewsItem(
                    index=idx,
                    title=title,
                    title_zh=title_zh,
                    content=content,
                    content_zh=content_zh,
                    source=source,
                    url=url,
                    published_at=published_at,
                )
            )

        return items

    except ExternalServiceError:
        raise
    except Exception as exc:
        raise ExternalServiceError(f"Marketaux news request failed: {exc}") from exc
