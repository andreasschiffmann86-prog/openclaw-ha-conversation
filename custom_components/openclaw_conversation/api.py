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

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

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
