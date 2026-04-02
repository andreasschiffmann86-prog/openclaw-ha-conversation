"""Async HTTP client for the OpenClaw API."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class OpenClawApiError(Exception):
    """Base exception for OpenClaw API errors."""


class OpenClawConnectionError(OpenClawApiError):
    """Raised when a network connection error occurs."""


class OpenClawTimeoutError(OpenClawApiError):
    """Raised when the request times out."""


class OpenClawAuthError(OpenClawApiError):
    """Raised when authentication fails (HTTP 401/403)."""


class OpenClawApiClient:
    """Async HTTP client for the OpenClaw conversation API."""

    def __init__(
        self,
        api_url: str,
        api_key: str | None,
        timeout: int,
        session: aiohttp.ClientSession,
    ) -> None:
        self._base_url = api_url.rstrip("/")
        self._api_key = api_key or None
        self._timeout = timeout
        self._session = session

    def _auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def async_check_reachability(self) -> None:
        """Verify that OpenClaw is reachable and the API key is accepted.

        Tries GET /{health,ping,""} in order and accepts any HTTP response
        (including 404) as proof of connectivity.  Only network-level errors,
        timeouts and auth rejections raise exceptions.
        """
        probe_paths = ("/health", "/ping", "/")
        last_exc: Exception | None = None

        for path in probe_paths:
            url = f"{self._base_url}{path}"
            try:
                async with self._session.get(
                    url,
                    headers=self._auth_headers(),
                    timeout=aiohttp.ClientTimeout(total=min(self._timeout, 10)),
                ) as resp:
                    if resp.status in (401, 403):
                        raise OpenClawAuthError(
                            f"Authentication failed (HTTP {resp.status})"
                        )
                    # Any other response means the server is reachable.
                    return
            except (OpenClawAuthError,):
                raise
            except asyncio.TimeoutError as exc:
                raise OpenClawTimeoutError("Connection test timed out") from exc
            except aiohttp.ClientConnectionError as exc:
                last_exc = exc
                continue  # try next probe path
            except aiohttp.ClientError as exc:
                raise OpenClawConnectionError(f"HTTP client error: {exc}") from exc

        raise OpenClawConnectionError(
            f"Cannot connect to {self._base_url}: {last_exc}"
        )

    async def async_send_message(
        self,
        message: str,
        conversation_id: str | None = None,
        language: str = "de",
        ha_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a message to OpenClaw and return the parsed JSON response.

        Expected response shape:
          {
            "response": "Antwort als Text",
            "conversation_id": "optional-session-id",
            "actions": [...]   # optional, Phase 2
          }
        """
        payload: dict[str, Any] = {
            "message": message,
            "language": language,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id
        if ha_context:
            payload["context"] = ha_context

        headers: dict[str, str] = {"Content-Type": "application/json", **self._auth_headers()}

        url = f"{self._base_url}/conversation"

        try:
            async with self._session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                if resp.status in (401, 403):
                    raise OpenClawAuthError(
                        f"Authentication failed (HTTP {resp.status})"
                    )
                if resp.status >= 400:
                    body = await resp.text()
                    raise OpenClawApiError(
                        f"API returned HTTP {resp.status}: {body[:200]}"
                    )
                return await resp.json()
        except asyncio.TimeoutError as exc:
            raise OpenClawTimeoutError(
                f"Request timed out after {self._timeout}s"
            ) from exc
        except aiohttp.ClientConnectionError as exc:
            raise OpenClawConnectionError(
                f"Cannot connect to {self._base_url}: {exc}"
            ) from exc
        except (OpenClawApiError, OpenClawTimeoutError, OpenClawConnectionError):
            raise
        except aiohttp.ClientError as exc:
            raise OpenClawConnectionError(f"HTTP client error: {exc}") from exc

    async def async_send_message_with_retry(
        self,
        message: str,
        conversation_id: str | None = None,
        language: str = "de",
        ha_context: dict[str, Any] | None = None,
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        """Send a message with exponential-backoff retry on transient errors.

        Retries only on connection/timeout failures (bridge flap).
        Auth errors and API errors (4xx) are re-raised immediately.
        Backoff: 0.5 s, 1 s, 2 s between attempts.
        """
        last_exc: OpenClawApiError | None = None
        for attempt in range(max_attempts):
            try:
                return await self.async_send_message(
                    message=message,
                    conversation_id=conversation_id,
                    language=language,
                    ha_context=ha_context,
                )
            except (OpenClawAuthError, OpenClawApiError):
                raise  # not retryable
            except (OpenClawConnectionError, OpenClawTimeoutError) as exc:
                last_exc = exc
                if attempt < max_attempts - 1:
                    backoff = 0.5 * (2 ** attempt)  # 0.5 s, 1 s, 2 s
                    _LOGGER.debug(
                        "OpenClaw send failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1,
                        max_attempts,
                        backoff,
                        exc,
                    )
                    await asyncio.sleep(backoff)

        raise last_exc  # type: ignore[misc]
