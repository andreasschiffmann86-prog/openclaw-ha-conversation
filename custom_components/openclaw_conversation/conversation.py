"""OpenClaw conversation agent entity."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.conversation import (
    ConversationEntity,
    ConversationInput,
    ConversationResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import (
    OpenClawApiClient,
    OpenClawApiError,
    OpenClawConnectionError,
    OpenClawTimeoutError,
)
from .const import (
    CONF_AGENT_NAME,
    CONF_SEND_HA_CONTEXT,
    DEFAULT_AGENT_NAME,
    DEFAULT_SEND_HA_CONTEXT,
    DOMAIN,
    HA_CONTEXT_DOMAINS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the OpenClaw conversation entity from a config entry."""
    client: OpenClawApiClient = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([OpenClawConversationEntity(hass, config_entry, client)])


class OpenClawConversationEntity(ConversationEntity):
    """Conversation entity that delegates to the OpenClaw API."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:robot"

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: OpenClawApiClient,
    ) -> None:
        config = {**config_entry.data, **config_entry.options}
        self._client = client
        self._send_context = config.get(CONF_SEND_HA_CONTEXT, DEFAULT_SEND_HA_CONTEXT)
        self._attr_unique_id = config_entry.entry_id
        self._attr_name = config.get(CONF_AGENT_NAME, DEFAULT_AGENT_NAME)
        self.hass = hass

    @property
    def supported_languages(self) -> list[str] | str:
        """Accept all languages; OpenClaw handles language routing."""
        return MATCH_ALL

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Process an incoming user message and return the agent response."""
        ha_context: dict[str, Any] | None = (
            self._build_ha_context() if self._send_context else None
        )

        conversation_id = user_input.conversation_id
        response_text: str

        try:
            data = await self._client.async_send_message(
                message=user_input.text,
                conversation_id=conversation_id,
                language=user_input.language,
                ha_context=ha_context,
            )
        except OpenClawTimeoutError as err:
            _LOGGER.warning("OpenClaw request timed out: %s", err)
            response_text = _msg_timeout(user_input.language)
        except OpenClawConnectionError as err:
            _LOGGER.error("OpenClaw connection error: %s", err)
            response_text = _msg_connection_error(user_input.language)
        except OpenClawApiError as err:
            _LOGGER.error("OpenClaw API error: %s", err)
            response_text = _msg_api_error(user_input.language, detail=str(err))
        else:
            response_text = data.get("response", "")
            # Keep the server-assigned conversation_id when provided.
            conversation_id = data.get("conversation_id", conversation_id)

            # Phase 2 placeholder: log actions returned by the API.
            if actions := data.get("actions"):
                _LOGGER.debug(
                    "OpenClaw returned %d action(s) — execution not yet implemented",
                    len(actions),
                )

        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(response_text)
        return ConversationResult(
            response=intent_response,
            conversation_id=conversation_id or user_input.conversation_id,
        )

    def _build_ha_context(self) -> dict[str, Any]:
        """Collect current HA device states and return them as context payload."""
        entities = [
            {
                "entity_id": state.entity_id,
                "state": state.state,
                "name": state.attributes.get("friendly_name", state.entity_id),
            }
            for state in self.hass.states.async_all()
            if state.domain in HA_CONTEXT_DOMAINS
        ]
        return {"ha_entities": entities}


# ---------------------------------------------------------------------------
# Localised error messages (de / en fallback)
# ---------------------------------------------------------------------------

def _msg_timeout(lang: str) -> str:
    if lang.startswith("de"):
        return "Die Anfrage hat zu lange gedauert. Bitte versuche es erneut."
    return "The request timed out. Please try again."


def _msg_connection_error(lang: str) -> str:
    if lang.startswith("de"):
        return "Verbindung zu James nicht möglich. Bitte prüfe die Konfiguration."
    return "Cannot connect to James. Please check the configuration."


def _msg_api_error(lang: str, detail: str = "") -> str:
    if lang.startswith("de"):
        msg = "James: API-Fehler."
    else:
        msg = "James: API error."
    if detail:
        msg = f"{msg} ({detail})"
    return msg
