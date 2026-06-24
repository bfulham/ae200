"""Binary sensor platform for Mitsubishi AE-200."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_CHECK_WATER,
    ATTR_ENERGY_CONTROL,
    ATTR_ERROR_SIGN,
    ATTR_FILTER_SIGN,
    ATTR_HOLD,
    ATTR_MODE_STATUS,
    ATTR_OCCUPANCY,
    ATTR_REMOTE_CONTROL,
    ATTR_SCHEDULE,
    ATTR_SCHEDULE_AVAILABLE,
)
from .entity import AE200GroupEntity
from .models import is_on_value, is_problem_value


@dataclass(frozen=True, slots=True)
class BinaryDescription:
    key: str
    name: str
    value_fn: Callable[[dict[str, str]], bool | None]
    device_class: BinarySensorDeviceClass | None = None
    icon: str | None = None
    enabled_default: bool = False


def _optional_active(value: object) -> bool | None:
    """Return None when the controller supplied no sensor value."""

    text = str(value or "").strip()
    if text in {"", "*", "--"}:
        return None
    return is_on_value(text)


BINARY_SENSORS = (
    BinaryDescription(
        key="error",
        name="Error",
        value_fn=lambda status: is_problem_value(
            status.get(ATTR_ERROR_SIGN)
        ),
        device_class=BinarySensorDeviceClass.PROBLEM,
        enabled_default=True,
    ),
    BinaryDescription(
        key="filter",
        name="Filter service",
        value_fn=lambda status: is_on_value(
            status.get(ATTR_FILTER_SIGN)
        ),
        device_class=BinarySensorDeviceClass.PROBLEM,
        enabled_default=True,
    ),
    BinaryDescription(
        key="check_water",
        name="Check water",
        value_fn=lambda status: is_problem_value(
            status.get(ATTR_CHECK_WATER)
        ),
        device_class=BinarySensorDeviceClass.PROBLEM,
        enabled_default=True,
    ),
    BinaryDescription(
        key="schedule",
        name="Schedule active",
        value_fn=lambda status: is_on_value(
            status.get(ATTR_SCHEDULE)
        ),
        icon="mdi:calendar-clock",
    ),
    BinaryDescription(
        key="hold",
        name="Hold active",
        value_fn=lambda status: is_on_value(
            status.get(ATTR_HOLD)
        ),
        icon="mdi:pause-circle",
    ),
    BinaryDescription(
        key="energy_control",
        name="Energy control active",
        value_fn=lambda status: is_on_value(
            status.get(ATTR_ENERGY_CONTROL)
        ),
        icon="mdi:leaf",
    ),
    BinaryDescription(
        key="remote_control_permitted",
        name="Remote control permitted",
        value_fn=lambda status: is_on_value(
            status.get(ATTR_REMOTE_CONTROL)
        ),
        icon="mdi:remote",
    ),
    BinaryDescription(
        key="mode_control_enabled",
        name="Mode control enabled",
        value_fn=lambda status: is_on_value(
            status.get(ATTR_MODE_STATUS)
        ),
        icon="mdi:lock-open-variant",
    ),
    BinaryDescription(
        key="occupancy",
        name="Occupancy",
        value_fn=lambda status: _optional_active(
            status.get(ATTR_OCCUPANCY)
        ),
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        enabled_default=False,
    ),
    BinaryDescription(
        key="schedule_available",
        name="Schedule available",
        value_fn=lambda status: is_on_value(
            status.get(ATTR_SCHEDULE_AVAILABLE)
        ),
        icon="mdi:calendar-check",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AE-200 binary sensors."""

    coordinator = entry.runtime_data.coordinator
    known_groups: set[str] = set()

    @callback
    def async_add_new_groups() -> None:
        entities = []
        for group_id, group in coordinator.data.groups.items():
            if group_id in known_groups:
                continue
            known_groups.add(group_id)
            entities.extend(
                AE200GroupBinarySensor(
                    coordinator,
                    entry.entry_id,
                    group,
                    description,
                )
                for description in BINARY_SENSORS
            )
        if entities:
            async_add_entities(entities)

    async_add_new_groups()
    entry.async_on_unload(
        coordinator.async_add_listener(async_add_new_groups)
    )


class AE200GroupBinarySensor(
    AE200GroupEntity,
    BinarySensorEntity,
):
    """One AE-200 diagnostic binary sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator,
        entry_id,
        group,
        description: BinaryDescription,
    ) -> None:
        super().__init__(
            coordinator,
            entry_id,
            group,
            description.key,
        )
        self.description = description
        self._attr_name = description.name
        self._attr_device_class = description.device_class
        self._attr_icon = description.icon
        self._attr_entity_registry_enabled_default = (
            description.enabled_default
        )

    @property
    def is_on(self) -> bool | None:
        return self.description.value_fn(dict(self.status))
