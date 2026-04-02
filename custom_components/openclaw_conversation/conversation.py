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
from .supervisor import BridgeSupervisor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the OpenClaw conversation entity from a config entry."""
    entry_data: dict = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [OpenClawConversationEntity(hass, config_entry, entry_data["client"], entry_data["supervisor"])]
    )


class OpenClawConversationEntity(ConversationEntity):
    """Conversation entity that delegates to the OpenClaw API.

    Availability is driven by the BridgeSupervisor circuit breaker:
    - CLOSED / HALF_OPEN → available, requests go through (with retry)
    - OPEN               → unavailable, fast-fail without HTTP attempt
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:robot"

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: OpenClawApiClient,
        supervisor: BridgeSupervisor,
    ) -> None:
        config = {**config_entry.data, **config_entry.options}
        self._client = client
        self._supervisor = supervisor
        self._send_context = config.get(CONF_SEND_HA_CONTEXT, DEFAULT_SEND_HA_CONTEXT)
        self._attr_unique_id = config_entry.entry_id
        self._attr_name = config.get(CONF_AGENT_NAME, DEFAULT_AGENT_NAME)
        self.hass = hass

        # Register with the supervisor so we get notified on circuit state changes.
        supervisor.add_listener(self._on_supervisor_state_change)

    # ------------------------------------------------------------------
    # HA entity properties
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Entity is unavailable when the circuit breaker is OPEN."""
        return self._supervisor.is_available

    @property
    def supported_languages(self) -> list[str] | str:
        """Accept all languages; OpenClaw handles language routing."""
        return MATCH_ALL

    # ------------------------------------------------------------------
    # Supervisor callback
    # ------------------------------------------------------------------

    def _on_supervisor_state_change(self) -> None:
        """Called by BridgeSupervisor when circuit state changes."""
        _LOGGER.debug(
            "Circuit state changed → %s, updating entity availability",
            self._supervisor.state.value,
        )
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Conversation processing
    # ------------------------------------------------------------------

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Process an incoming user message and return the agent response."""

        # Fast-fail when the circuit is OPEN — no HTTP attempt, instant reply.
        if not self._supervisor.is_available:
            _LOGGER.warning("OpenClaw circuit OPEN — fast-failing request")
            response_text = _msg_bridge_offline(user_input.language)
            return self._build_result(response_text, user_input)

        ha_context: dict[str, Any] | None = (
            self._build_ha_context() if self._send_context else None
        )

        conversation_id = user_input.conversation_id
        response_text: str

        try:
            data = await self._client.async_send_message_with_retry(
                message=user_input.text,
                conversation_id=conversation_id,
                language=user_input.language,
                ha_context=ha_context,
            )
        except OpenClawTimeoutError as err:
            _LOGGER.warning("OpenClaw request timed out: %s", err)
            self._supervisor.report_failure()
            response_text = _msg_timeout(user_input.language)
        except OpenClawConnectionError as err:
            _LOGGER.error("OpenClaw connection error: %s", err)
            self._supervisor.report_failure()
            response_text = _msg_connection_error(user_input.language)
        except OpenClawApiError as err:
            _LOGGER.error("OpenClaw API error: %s", err)
            # API errors (4xx/5xx) don't count as bridge failures.
            response_text = _msg_api_error(user_input.language, detail=str(err))
        else:
            self._supervisor.report_success()
            response_text = data.get("response", "")
            conversation_id = data.get("conversation_id", conversation_id)

            # Phase 2 placeholder: log actions returned by the API.
            if actions := data.get("actions"):
                _LOGGER.debug(
                    "OpenClaw returned %d action(s) — execution not yet implemented",
                    len(actions),
                )

        return self._build_result(response_text, user_input, conversation_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_result(
        self,
        speech: str,
        user_input: ConversationInput,
        conversation_id: str | None = None,
    ) -> ConversationResult:
        intent_response = intent.IntentResponse(language=user_input.language)
        intent_response.async_set_speech(speech)
        return ConversationResult(
            response=intent_response,
            conversation_id=conversation_id or user_input.conversation_id,
        )

    def _build_ha_context(self) -> dict[str, Any]:
        """Collect current HA device states as context payload."""
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

def _msg_bridge_offline(lang: str) -> str:
    if lang.startswith("de"):
        return "James ist momentan nicht erreichbar (Bridge offline). Bitte warte kurz."
    return "James is currently unavailable (bridge offline). Please try again shortly."


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
