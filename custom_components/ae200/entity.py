"""Shared entity base classes for Mitsubishi AE-200."""

from __future__ import annotations

from typing import Mapping

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONTROLLER_MODEL,
    DOMAIN,
    INDOOR_UNIT_MODEL,
    MANUFACTURER,
)
from .coordinator import AE200Coordinator
from .protocol import AE200Group


class AE200GroupEntity(CoordinatorEntity[AE200Coordinator]):
    """Base entity for one AE-200 group."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AE200Coordinator,
        entry_id: str,
        group: AE200Group,
        entity_key: str,
    ) -> None:
        super().__init__(coordinator)
        self.group_id = group.group_id
        self.group_name = group.name
        self._attr_unique_id = (
            f"{entry_id}_group_{group.group_id}_{entity_key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{entry_id}_group_{group.group_id}")
            },
            name=group.name,
            manufacturer=MANUFACTURER,
            model=INDOOR_UNIT_MODEL,
            via_device=(DOMAIN, entry_id),
        )

    @property
    def status(self) -> Mapping[str, str]:
        """Return current cached group status."""

        if self.coordinator.data is None:
            return {}
        return self.coordinator.data.statuses.get(self.group_id, {})

    @property
    def available(self) -> bool:
        """Return whether the group is available."""

        return super().available and bool(self.status)


class AE200ControllerEntity(CoordinatorEntity[AE200Coordinator]):
    """Base entity attached to the AE-200 controller device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AE200Coordinator,
        entry_id: str,
        controller_name: str,
        entity_key: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_controller_{entity_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=controller_name,
            manufacturer=MANUFACTURER,
            model=CONTROLLER_MODEL,
        )
