"""OpenClaw Conversation Agent — Home Assistant Integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OpenClawApiClient
from .const import (
    CONF_API_KEY,
    CONF_API_URL,
    CONF_TIMEOUT,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .supervisor import BridgeSupervisor

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CONVERSATION]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenClaw Conversation Agent from a config entry."""
    config = {**entry.data, **entry.options}

    client = OpenClawApiClient(
        api_url=config[CONF_API_URL],
        api_key=config.get(CONF_API_KEY) or None,
        timeout=config.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        session=async_get_clientsession(hass),
    )

    supervisor = BridgeSupervisor(client)
    await supervisor.async_start(hass)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "supervisor": supervisor,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    entry.async_on_unload(supervisor.async_stop)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
