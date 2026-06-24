"""Button platform for Mitsubishi AE-200."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_NAME, DEFAULT_NAME
from .entity import AE200ControllerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up controller buttons."""

    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            AE200RefreshButton(
                coordinator,
                entry.entry_id,
                entry.data.get(
                    CONF_NAME,
                    entry.title or DEFAULT_NAME,
                ),
            )
        ]
    )


class AE200RefreshButton(
    AE200ControllerEntity,
    ButtonEntity,
):
    """Force group rediscovery and an immediate refresh."""

    _attr_name = "Rediscover and refresh"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator,
        entry_id: str,
        controller_name: str,
    ) -> None:
        super().__init__(
            coordinator,
            entry_id,
            controller_name,
            "rediscover_refresh",
        )

    async def async_press(self) -> None:
        await self.coordinator.async_force_rediscovery()
