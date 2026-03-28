"""Config flow for OpenClaw Conversation Agent."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    OpenClawApiClient,
    OpenClawAuthError,
    OpenClawConnectionError,
    OpenClawTimeoutError,
)
from .const import (
    CONF_AGENT_NAME,
    CONF_API_KEY,
    CONF_API_URL,
    CONF_SEND_HA_CONTEXT,
    CONF_TIMEOUT,
    DEFAULT_AGENT_NAME,
    DEFAULT_SEND_HA_CONTEXT,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _build_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_API_URL, default=defaults.get(CONF_API_URL, "http://localhost:8080")): str,
            vol.Optional(CONF_API_KEY, default=defaults.get(CONF_API_KEY, "")): str,
            vol.Optional(CONF_AGENT_NAME, default=defaults.get(CONF_AGENT_NAME, DEFAULT_AGENT_NAME)): str,
            vol.Optional(
                CONF_TIMEOUT,
                default=defaults.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
            vol.Optional(
                CONF_SEND_HA_CONTEXT,
                default=defaults.get(CONF_SEND_HA_CONTEXT, DEFAULT_SEND_HA_CONTEXT),
            ): bool,
        }
    )


async def _validate_connection(hass, user_input: dict[str, Any]) -> str | None:
    """Check that OpenClaw is reachable and the API key is valid.

    Uses GET /health (with fallbacks) so the /conversation endpoint does not
    need to exist yet.  Returns an error key string or None on success.
    """
    client = OpenClawApiClient(
        api_url=user_input[CONF_API_URL],
        api_key=user_input.get(CONF_API_KEY) or None,
        timeout=user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        session=async_get_clientsession(hass),
    )
    try:
        await client.async_check_reachability()
    except OpenClawAuthError:
        return "invalid_auth"
    except OpenClawTimeoutError:
        return "timeout"
    except OpenClawConnectionError:
        return "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected error during OpenClaw connection test")
        return "unknown"
    return None


class OpenClawConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            error = await _validate_connection(self.hass, user_input)
            if error:
                errors["base"] = error
            else:
                title = user_input.get(CONF_AGENT_NAME, DEFAULT_AGENT_NAME)
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(user_input or {}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return OpenClawOptionsFlow(config_entry)


class OpenClawOptionsFlow(config_entries.OptionsFlow):
    """Handle option updates after initial setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        super().__init__()
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}
        current = {**self._entry.data, **self._entry.options}

        if user_input is not None:
            error = await _validate_connection(self.hass, user_input)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(user_input or current),
            errors=errors,
        )
