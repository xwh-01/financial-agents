import httpx

from app.config import settings
from app.errors import ExternalServiceNotConfigured, ExternalServiceError


async def chat_completion(system_prompt: str, user_prompt: str) -> str:
    if not settings.llm_api_key:
        raise ExternalServiceNotConfigured("LLM_API_KEY is not configured.")

    if not settings.llm_base_url:
        raise ExternalServiceNotConfigured("LLM_BASE_URL is not configured.")

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }

    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                settings.llm_base_url,
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise ExternalServiceError(f"LLM request failed: {exc}") from exc