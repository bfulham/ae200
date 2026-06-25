"""Diagnostics for Mitsubishi AE-200."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN


def _data_to_dict(data) -> dict[str, Any]:
    return {
        "groups": {
            group_id: {
                "name": group.name,
                "discovery_attributes": dict(
                    group.discovery_attributes
                ),
            }
            for group_id, group in data.groups.items()
        },
        "statuses": {
            group_id: dict(status)
            for group_id, status in data.statuses.items()
        },
        "protocol_errors": [
            dict(error) for error in data.protocol_errors
        ],
        "summary": {
            "group_count": data.group_count,
            "running_count": data.running_count,
            "fault_count": data.fault_count,
            "filter_alert_count": data.filter_alert_count,
            "scheduled_count": data.scheduled_count,
            "raw_modes": list(data.raw_modes),
            "stale_groups": sorted(data.stale_groups),
            "stale_group_count": data.stale_group_count,
            "using_stale_data": data.using_stale_data,
            "consecutive_poll_failures": data.consecutive_poll_failures,
            "last_poll_error": data.last_poll_error,
        },
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return redacted config-entry diagnostics."""

    coordinator = entry.runtime_data.coordinator
    return {
        "entry": async_redact_data(
            {
                "title": entry.title,
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            {CONF_HOST},
        ),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": (
                str(coordinator.last_exception)
                if coordinator.last_exception
                else None
            ),
            "last_write_error": coordinator.last_write_error,
            "last_poll_error": coordinator.last_poll_error,
            "consecutive_poll_failures": coordinator.consecutive_poll_failures,
            "using_stale_data": coordinator.using_stale_data,
            "update_interval": str(coordinator.update_interval),
        },
        "controller_data": _data_to_dict(coordinator.data),
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: DeviceEntry,
) -> dict[str, Any]:
    """Return diagnostics for one controller or group device."""

    coordinator = entry.runtime_data.coordinator

    controller_identifier = (DOMAIN, entry.entry_id)
    if controller_identifier in device.identifiers:
        return await async_get_config_entry_diagnostics(hass, entry)

    prefix = f"{entry.entry_id}_group_"
    group_id = None
    for domain, identifier in device.identifiers:
        if domain == DOMAIN and identifier.startswith(prefix):
            group_id = identifier[len(prefix):]
            break

    if group_id is None:
        return {"error": "Unable to identify AE-200 group"}

    group = coordinator.data.groups.get(group_id)
    return {
        "group": {
            "id": group_id,
            "name": group.name if group else None,
            "discovery_attributes": (
                dict(group.discovery_attributes) if group else {}
            ),
            "status": dict(
                coordinator.data.statuses.get(group_id, {})
            ),
            "data_stale": group_id in coordinator.data.stale_groups,
        }
    }
