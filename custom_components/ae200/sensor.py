"""Sensor platform for Mitsubishi AE-200."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_AIR_DIRECTION,
    ATTR_FAN_SPEED,
    ATTR_INLET_HUMIDITY,
    ATTR_INLET_TEMP,
    ATTR_MODE,
    ATTR_OUTDOOR_TEMP,
    ATTR_SET_TEMP,
    CONF_NAME,
    DEFAULT_NAME,
)
from .entity import AE200ControllerEntity, AE200GroupEntity
from .models import as_float


@dataclass(frozen=True, slots=True)
class GroupSensorDescription:
    key: str
    name: str
    value_fn: Callable[[dict[str, str]], object]
    device_class: SensorDeviceClass | None = None
    unit: str | None = None
    state_class: SensorStateClass | None = None
    icon: str | None = None
    enabled_default: bool = False


GROUP_SENSORS = (
    GroupSensorDescription(
        key="room_temperature",
        name="Room temperature",
        value_fn=lambda status: as_float(status.get(ATTR_INLET_TEMP)),
        device_class=SensorDeviceClass.TEMPERATURE,
        unit=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        enabled_default=False,
    ),
    GroupSensorDescription(
        key="target_temperature",
        name="Target temperature",
        value_fn=lambda status: as_float(status.get(ATTR_SET_TEMP)),
        device_class=SensorDeviceClass.TEMPERATURE,
        unit=UnitOfTemperature.CELSIUS,
        enabled_default=False,
    ),
    GroupSensorDescription(
        key="humidity",
        name="Inlet humidity",
        value_fn=lambda status: (
            value
            if (value := as_float(status.get(ATTR_INLET_HUMIDITY)))
            is not None
            and value > 0
            else None
        ),
        device_class=SensorDeviceClass.HUMIDITY,
        unit=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        enabled_default=False,
    ),
    GroupSensorDescription(
        key="outdoor_temperature",
        name="Outdoor temperature",
        value_fn=lambda status: as_float(status.get(ATTR_OUTDOOR_TEMP)),
        device_class=SensorDeviceClass.TEMPERATURE,
        unit=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        enabled_default=False,
    ),
    GroupSensorDescription(
        key="raw_mode",
        name="Raw mode",
        value_fn=lambda status: status.get(ATTR_MODE) or None,
        icon="mdi:hvac",
        enabled_default=False,
    ),
    GroupSensorDescription(
        key="fan_speed",
        name="Fan speed",
        value_fn=lambda status: status.get(ATTR_FAN_SPEED) or None,
        icon="mdi:fan",
        enabled_default=False,
    ),
    GroupSensorDescription(
        key="air_direction",
        name="Air direction",
        value_fn=lambda status: status.get(ATTR_AIR_DIRECTION) or None,
        icon="mdi:arrow-expand-vertical",
        enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AE-200 sensors."""

    coordinator = entry.runtime_data.coordinator
    known_groups: set[str] = set()

    controller_name = entry.data.get(
        CONF_NAME,
        entry.title or DEFAULT_NAME,
    )
    controller_entities: list[SensorEntity] = []
    for key, name, icon in (
        ("group_count", "Configured groups", "mdi:air-conditioner"),
        ("running_count", "Running groups", "mdi:power"),
        ("fault_count", "Groups with faults", "mdi:alert-circle"),
        ("filter_alert_count", "Filter alerts", "mdi:air-filter"),
        ("scheduled_count", "Scheduled groups", "mdi:calendar-clock"),
    ):
        controller_entities.append(
            AE200ControllerCountSensor(
                coordinator,
                entry.entry_id,
                controller_name,
                key,
                name,
                icon,
            )
        )
    async_add_entities(controller_entities)

    @callback
    def async_add_new_groups() -> None:
        entities: list[SensorEntity] = []
        for group_id, group in coordinator.data.groups.items():
            if group_id in known_groups:
                continue
            known_groups.add(group_id)
            entities.extend(
                AE200GroupSensor(
                    coordinator,
                    entry.entry_id,
                    group,
                    description,
                )
                for description in GROUP_SENSORS
            )
        if entities:
            async_add_entities(entities)

    async_add_new_groups()
    entry.async_on_unload(
        coordinator.async_add_listener(async_add_new_groups)
    )


class AE200GroupSensor(AE200GroupEntity, SensorEntity):
    """Diagnostic sensor for one group."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator,
        entry_id,
        group,
        description: GroupSensorDescription,
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
        self._attr_native_unit_of_measurement = description.unit
        self._attr_state_class = description.state_class
        self._attr_icon = description.icon
        self._attr_entity_registry_enabled_default = (
            description.enabled_default
        )

    @property
    def native_value(self):
        return self.description.value_fn(dict(self.status))


class AE200ControllerCountSensor(
    AE200ControllerEntity,
    SensorEntity,
):
    """Controller summary count."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "groups"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator,
        entry_id: str,
        controller_name: str,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        super().__init__(
            coordinator,
            entry_id,
            controller_name,
            key,
        )
        self.key = key
        self._attr_name = name
        self._attr_icon = icon

    @property
    def native_value(self) -> int:
        data = self.coordinator.data
        if self.key == "group_count":
            return data.group_count
        if self.key == "running_count":
            return data.running_count
        if self.key == "fault_count":
            return data.fault_count
        if self.key == "filter_alert_count":
            return data.filter_alert_count
        if self.key == "scheduled_count":
            return data.scheduled_count
        return 0
