# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] - 2026-04-02

### Added
- `BridgeSupervisor` background task (`supervisor.py`) with 3-state circuit breaker
  (CLOSED → OPEN → HALF_OPEN) that monitors the OpenClaw HTTP bridge continuously
- Circuit breaker trips after 3 consecutive failures; probes recovery every 10 s
- When circuit is OPEN: requests fast-fail instantly with localised message (no 30 s wait)
- Conversation entity `available` property reflects circuit state — HA shows entity as
  unavailable when bridge is down
- Retry logic in `api.py` (`async_send_message_with_retry`): up to 3 attempts with
  exponential backoff (0.5 s / 1 s / 2 s) for transient connection/timeout errors
- `report_failure()` / `report_success()` hooks so conversation entity feeds signal back
  to supervisor without waiting for the next scheduled health probe

### Changed
- `__init__.py`: stores `{"client": ..., "supervisor": ...}` dict per entry instead of
  bare client; supervisor lifecycle tied to config entry via `async_on_unload`
- `conversation.py`: uses retry-aware send method; notifies supervisor of outcomes
- `const.py`: version bump to `1.1.0`

---

## [1.0.0] - 2026-03-28

### Added
- Initial release
- OpenClaw (James) as a native conversation agent in Home Assistant
- Config Flow — full UI setup, no YAML required
- Options Flow — change settings without reinstalling
- German and English translations
- Optional: send current HA device state as context with every request
- Compatible with HA Voice / Wyoming speech pipeline
- Graceful error handling for timeouts, connection errors and API failures
- Automatic integration reload on settings change
- Phase 2 placeholder: `actions` returned by the API are logged but not yet executed
