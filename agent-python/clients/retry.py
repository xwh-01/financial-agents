import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from app.errors import ExternalServiceError


@dataclass
class ExternalAPIError(ExternalServiceError):
    error_type: str
    message: str
    status_code: int | None = None

    def __str__(self) -> str:
        status = f", status={self.status_code}" if self.status_code else ""
        return f"{self.error_type}: {self.message}{status}"


async def get_json_with_retry(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30,
    max_retries: int = 3,
    backoff_seconds: float = 1.0,
    error_type: str,
) -> dict[str, Any]:
    response = await get_with_retry(
        url,
        params=params,
        headers=headers,
        timeout=timeout,
        max_retries=max_retries,
        backoff_seconds=backoff_seconds,
        error_type=error_type,
    )
    try:
        data = response.json()
    except ValueError as exc:
        raise ExternalAPIError("invalid_response", f"invalid JSON from {url}") from exc
    if not isinstance(data, dict):
        raise ExternalAPIError("invalid_response", f"expected JSON object from {url}")
    return data


async def get_bytes_with_retry(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 30,
    max_retries: int = 3,
    backoff_seconds: float = 1.0,
    error_type: str,
) -> bytes:
    response = await get_with_retry(
        url,
        headers=headers,
        timeout=timeout,
        max_retries=max_retries,
        backoff_seconds=backoff_seconds,
        error_type=error_type,
    )
    return response.content


async def get_with_retry(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30,
    max_retries: int = 3,
    backoff_seconds: float = 1.0,
    error_type: str,
) -> httpx.Response:
    attempts = max(1, max_retries)
    last_error: Exception | None = None

    for attempt in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(url, params=params, headers=headers)
            if response.status_code == 429:
                raise ExternalAPIError("rate_limited", "external API rate limited", 429)
            if response.status_code >= 400:
                raise ExternalAPIError(error_type, response.text[:300], response.status_code)
            return response
        except httpx.TimeoutException as exc:
            last_error = ExternalAPIError("timeout", f"request timed out for {url}: {exc}")
        except ExternalAPIError as exc:
            last_error = exc
            if exc.error_type in {"rate_limited", "invalid_response"}:
                break
        except Exception as exc:
            last_error = ExternalAPIError(error_type, str(exc))

        if attempt < attempts - 1:
            await asyncio.sleep(backoff_seconds * (2**attempt))

    if isinstance(last_error, ExternalAPIError):
        raise last_error
    raise ExternalAPIError(error_type, f"request failed for {url}")
