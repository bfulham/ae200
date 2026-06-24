# Changelog

## 0.1.0 — 2026-06-24

- Initial hardware-test release.
- UI config flow and host reconfiguration.
- Batched polling of all AE-200 groups.
- Climate control for power, Heat, Cool, Auto, temperature, fan and air direction.
- Correct Auto command/read-back mapping (`AUTO` → `AUTOCOOL` or `AUTOHEAT`).
- Serialized, exact-group writes with selected-group read-back verification.
- Per-group fault, filter, water, schedule, hold, occupancy and control-status diagnostics.
- Controller summary sensors and rediscovery button.
- Config-entry and device diagnostics.
- Legacy YAML import.
- Uses Home Assistant's shared aiohttp session; no additional Python dependency.
- Status request tailored to the supplied 42-group controller dump.
