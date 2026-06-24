"""Mitsubishi AE-200 integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_NAME,
    CONF_TIMEOUT,
    CONTROLLER_MODEL,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import AE200Coordinator
from .protocol import AE200Client


@dataclass(slots=True)
class AE200RuntimeData:
    """Runtime data stored on the config entry."""

    client: AE200Client
    coordinator: AE200Coordinator


AE200ConfigEntry = ConfigEntry[AE200RuntimeData]

PLATFORMS = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]


async def async_setup(
    hass: HomeAssistant,
    config: dict,
) -> bool:
    """Set up the integration namespace."""

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AE200ConfigEntry,
) -> bool:
    """Set up an AE-200 config entry."""

    timeout = float(entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT))
    client = AE200Client(
        entry.data[CONF_HOST],
        async_get_clientsession(hass),
        timeout=timeout,
    )
    coordinator = AE200Coordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = AE200RuntimeData(
        client=client,
        coordinator=coordinator,
    )

    controller_name = entry.data.get(CONF_NAME, entry.title or DEFAULT_NAME)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=controller_name,
        manufacturer=MANUFACTURER,
        model=CONTROLLER_MODEL,
    )

    entry.async_on_unload(
        entry.add_update_listener(_async_reload_entry)
    )
    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: AE200ConfigEntry,
) -> bool:
    """Unload an AE-200 config entry."""

    return await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )


async def _async_reload_entry(
    hass: HomeAssistant,
    entry: AE200ConfigEntry,
) -> None:
    """Reload when options change."""

    await hass.config_entries.async_reload(entry.entry_id)
