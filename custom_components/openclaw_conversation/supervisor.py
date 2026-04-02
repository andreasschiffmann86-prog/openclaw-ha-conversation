"""BridgeSupervisor — Background watchdog with Circuit Breaker for OpenClaw.

States
------
CLOSED    Bridge is healthy. Requests pass through. Probed every 60 s.
OPEN      Bridge is down.   Requests fast-fail immediately. Probed every 10 s.
HALF_OPEN One probe request is in-flight to test recovery.
"""
from __future__ import annotations

import asyncio
import enum
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from .api import OpenClawApiClient

_LOGGER = logging.getLogger(__name__)


class CircuitState(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class BridgeSupervisor:
    """Monitors the OpenClaw HTTP bridge and exposes a circuit breaker.

    Usage
    -----
    supervisor = BridgeSupervisor(api_client)
    await supervisor.async_start(hass)
    ...
    entry.async_on_unload(supervisor.async_stop)
    """

    FAILURE_THRESHOLD = 3       # consecutive failures before OPEN
    PROBE_INTERVAL_CLOSED = 60  # seconds between health probes when CLOSED
    PROBE_INTERVAL_OPEN = 10    # seconds between recovery probes when OPEN

    def __init__(self, client: "OpenClawApiClient") -> None:
        self._client = client
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._task: asyncio.Task | None = None
        self._listeners: list[Callable[[], None]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """True when requests should be allowed through."""
        return self._state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    @property
    def state(self) -> CircuitState:
        return self._state

    def add_listener(self, callback: Callable[[], None]) -> None:
        """Register a callback that fires on every circuit state change."""
        self._listeners.append(callback)

    def report_failure(self) -> None:
        """Called by the conversation entity after a failed request."""
        self._failure_count += 1
        _LOGGER.debug(
            "OpenClaw failure reported (%d/%d)",
            self._failure_count,
            self.FAILURE_THRESHOLD,
        )
        if (
            self._state == CircuitState.CLOSED
            and self._failure_count >= self.FAILURE_THRESHOLD
        ):
            self._trip()

    def report_success(self) -> None:
        """Called by the conversation entity after a successful request."""
        if self._state != CircuitState.CLOSED:
            _LOGGER.info("OpenClaw bridge recovered — circuit CLOSED")
            self._state = CircuitState.CLOSED
            self._notify()
        self._failure_count = 0

    async def async_start(self, hass: "HomeAssistant") -> None:
        """Start the background health-check loop."""
        self._task = hass.async_create_background_task(
            self._run_loop(), name="openclaw_bridge_supervisor"
        )
        _LOGGER.debug("BridgeSupervisor started")

    async def async_stop(self) -> None:
        """Cancel the background task gracefully."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        _LOGGER.debug("BridgeSupervisor stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _trip(self) -> None:
        """Open the circuit — bridge is considered down."""
        _LOGGER.warning(
            "OpenClaw bridge unreachable after %d consecutive failures — circuit OPEN",
            self._failure_count,
        )
        self._state = CircuitState.OPEN
        self._notify()

    def _notify(self) -> None:
        for cb in self._listeners:
            try:
                cb()
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error in BridgeSupervisor listener")

    async def _probe(self) -> bool:
        """Perform one health probe. Returns True on success."""
        try:
            await self._client.async_check_reachability()
            return True
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("OpenClaw health probe failed: %s", exc)
            return False

    async def _run_loop(self) -> None:
        """Main background loop — probes the bridge and manages circuit state."""
        while True:
            if self._state == CircuitState.CLOSED:
                await asyncio.sleep(self.PROBE_INTERVAL_CLOSED)
                ok = await self._probe()
                if ok:
                    _LOGGER.debug("OpenClaw bridge healthy (circuit CLOSED)")
                    self._failure_count = 0
                else:
                    self._failure_count += 1
                    _LOGGER.debug(
                        "OpenClaw health probe failed (%d/%d)",
                        self._failure_count,
                        self.FAILURE_THRESHOLD,
                    )
                    if self._failure_count >= self.FAILURE_THRESHOLD:
                        self._trip()

            elif self._state == CircuitState.OPEN:
                await asyncio.sleep(self.PROBE_INTERVAL_OPEN)
                _LOGGER.debug("OpenClaw recovery probe (circuit OPEN)…")
                self._state = CircuitState.HALF_OPEN
                ok = await self._probe()
                if ok:
                    _LOGGER.info("OpenClaw bridge recovered — circuit CLOSED")
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._notify()
                else:
                    _LOGGER.debug("OpenClaw recovery probe failed — circuit stays OPEN")
                    self._state = CircuitState.OPEN

            else:
                # HALF_OPEN: a request is in-flight, sleep briefly and re-check
                await asyncio.sleep(1)
