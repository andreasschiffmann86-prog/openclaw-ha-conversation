# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
