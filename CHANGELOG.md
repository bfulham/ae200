# Changelog

## 1.1.1

- Fix the existing config entry **Configure** form returning a 500 error.
- Update the options flow for Home Assistant 2025.12 and newer by using
  the injected `self.config_entry` property.
- Repair the malformed maximum-temperature options schema.
- Prevent the reconfigure flow from combining its update listener with a
  second reload helper.

## 1.1.0

- Fix the existing-entry Configure form on Home Assistant 2025.12 and newer by using the injected `self.config_entry` options-flow property.
- Repair the malformed maximum-temperature field in the options schema.
- Avoid combining a config-entry update listener with the reconfigure reload helper.

- Prepare the integration for publication from `https://github.com/bfulham/ae200`.
- Update HACS metadata, badges, issue links, documentation and release automation for the final repository.
- Retain the existing AE-200 controller functionality and resilience behaviour.
- Include brand assets, HACS validation, Hassfest validation, issue templates and complete installation documentation.

## 0.2.0 — 2026-06-25

- Add HACS-ready repository metadata, required brand assets and validation workflows.
- Add complete installation, migration, diagnostics and support documentation.
- Add issue templates, contribution guidance and release automation.

- Retry failed discovery and status requests before treating a poll as failed.
- Retain the last successful state through short controller/network dropouts.
- Make the number of tolerated failed polls configurable.
- Do not take the integration offline when scheduled group rediscovery fails.
- Preserve previous values when an otherwise valid response omits individual groups.
- Add a diagnostic count of groups currently using cached data.
- Add stale-state and poll-failure details to downloaded diagnostics.
- Increase the default polling interval from 15 to 30 seconds and timeout from 8 to 10 seconds to reduce load on the controller.

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
