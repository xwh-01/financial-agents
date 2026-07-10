import asyncio
import logging

import httpx

from app.config import settings
from app.errors import ExternalServiceNotConfigured, ExternalServiceError

logger = logging.getLogger(__name__)


async def chat_completion(system_prompt: str, user_prompt: str) -> str:
    """
    Send a chat completion request to the configured LLM provider.

    Uses OpenAI-compatible API format. Retries on 429 (rate limit) and 5xx errors
    with exponential backoff. Raises ExternalServiceError on 4xx (except 429),
    JSON parse failures, or exhaustion of all retries.

    Configuration is drawn from settings: llm_api_key, llm_base_url, llm_model,
    llm_timeout_seconds, llm_retry_attempts, llm_retry_backoff_seconds.
    Temperature is fixed at 0.2 for deterministic output suitable for structured
    entity/event/risk extraction and report generation.
    """
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

    attempts = max(1, settings.llm_retry_attempts)
    backoff = max(0.0, settings.llm_retry_backoff_seconds)
    last_error = "unknown error"

    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        for attempt in range(1, attempts + 1):
            try:
                resp = await client.post(
                    settings.llm_base_url,
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                response_preview = exc.response.text[:500]
                last_error = f"HTTP {status_code}: {response_preview}"
                if status_code != 429 and status_code < 500:
                    raise ExternalServiceError(f"LLM request failed: {last_error}") from exc
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = str(exc)
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise ExternalServiceError(f"LLM response format is invalid: {exc}") from exc

            if attempt < attempts:
                sleep_seconds = backoff * (2 ** (attempt - 1))
                logger.info(
                    "retrying LLM request after attempt %s/%s failed: %s",
                    attempt,
                    attempts,
                    last_error,
                )
                await asyncio.sleep(sleep_seconds)

    raise ExternalServiceError(f"LLM request failed after {attempts} attempt(s): {last_error}")
