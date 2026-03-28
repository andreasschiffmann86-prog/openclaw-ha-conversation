"""Constants for OpenClaw Conversation Agent."""

DOMAIN = "openclaw_conversation"

CONF_API_URL = "api_url"
CONF_API_KEY = "api_key"
CONF_AGENT_NAME = "agent_name"
CONF_TIMEOUT = "timeout"
CONF_SEND_HA_CONTEXT = "send_ha_context"

DEFAULT_AGENT_NAME = "James"
DEFAULT_TIMEOUT = 30
DEFAULT_SEND_HA_CONTEXT = False

HA_CONTEXT_DOMAINS = frozenset(
    {"light", "switch", "climate", "cover", "fan", "lock", "media_player", "input_boolean"}
)

VERSION = "1.0.0"
