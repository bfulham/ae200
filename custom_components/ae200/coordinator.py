"""Data coordinator for Mitsubishi AE-200."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import time
from typing import Mapping

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_DRIVE,
    ATTR_MODE,
    CONF_TIMEOUT,
    CONF_UPDATE_INTERVAL,
    CONF_VERIFY_ATTEMPTS,
    CONF_VERIFY_WRITES,
    CONF_WRITE_DELAY,
    DEFAULT_TIMEOUT,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_VERIFY_ATTEMPTS,
    DEFAULT_VERIFY_WRITES,
    DEFAULT_WRITE_DELAY,
    DOMAIN,
)
from .models import AE200Data
from .protocol import (
    AE200Client,
    AE200ConnectionError,
    AE200Error,
    AE200Group,
    AE200WriteError,
    values_match,
)

_LOGGER = logging.getLogger(__name__)

REDISCOVERY_SECONDS = 30 * 60


class AE200Coordinator(DataUpdateCoordinator[AE200Data]):
    """Coordinate efficient controller-wide polling and serialized writes."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: AE200Client,
    ) -> None:
        self.entry = entry
        self.client = client
        self.groups: dict[str, AE200Group] = {}
        self._last_discovery = 0.0
        self._operation_lock = asyncio.Lock()
        self.last_write_error: str | None = None

        update_interval = int(
            entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
            always_update=False,
        )

    @property
    def verify_writes(self) -> bool:
        return bool(
            self.entry.options.get(CONF_VERIFY_WRITES, DEFAULT_VERIFY_WRITES)
        )

    @property
    def verification_attempts(self) -> int:
        return int(
            self.entry.options.get(
                CONF_VERIFY_ATTEMPTS,
                DEFAULT_VERIFY_ATTEMPTS,
            )
        )

    @property
    def write_delay(self) -> float:
        return float(
            self.entry.options.get(CONF_WRITE_DELAY, DEFAULT_WRITE_DELAY)
        )

    async def _async_update_data(self) -> AE200Data:
        """Fetch all group states in one coordinated operation."""

        try:
            async with self._operation_lock:
                now = time.monotonic()
                if (
                    not self.groups
                    or now - self._last_discovery >= REDISCOVERY_SECONDS
                ):
                    self.groups = await self.client.async_discover_groups()
                    self._last_discovery = now

                result = await self.client.async_get_status(self.groups)
        except AE200Error as exc:
            raise UpdateFailed(str(exc)) from exc

        if result.errors:
            _LOGGER.debug(
                "AE-200 returned protocol warnings: %s",
                result.errors,
            )

        return AE200Data(
            groups=dict(self.groups),
            statuses=dict(result.statuses),
            protocol_errors=result.errors,
        )

    async def async_force_rediscovery(self) -> None:
        """Rediscover groups on the next refresh."""

        self._last_discovery = 0.0
        await self.async_request_refresh()

    async def async_set_hvac_mode(
        self,
        group_id: str,
        raw_mode: str | None,
    ) -> None:
        """Set power/mode for exactly one group.

        For non-off modes this mirrors the reference integration: turn on the
        selected group when needed, then send the mode. AUTO is written as
        Mode="AUTO"; AUTOCOOL/AUTOHEAT are accepted on read-back.
        """

        async with self._operation_lock:
            try:
                status = self._status_for(group_id)
                expected: dict[str, str] = {}

                if raw_mode is None:
                    await self.client.async_set_attributes(
                        group_id,
                        {ATTR_DRIVE: "OFF"},
                    )
                    expected[ATTR_DRIVE] = "OFF"
                else:
                    if status.get(ATTR_DRIVE, "").upper() != "ON":
                        await self.client.async_set_attributes(
                            group_id,
                            {ATTR_DRIVE: "ON"},
                        )
                        expected[ATTR_DRIVE] = "ON"

                    if not values_match(
                        ATTR_MODE,
                        raw_mode,
                        status.get(ATTR_MODE, ""),
                    ):
                        await self.client.async_set_attributes(
                            group_id,
                            {ATTR_MODE: raw_mode},
                        )
                    expected[ATTR_MODE] = raw_mode
                    expected[ATTR_DRIVE] = "ON"

                await self._async_read_back_locked(group_id, expected)
            except HomeAssistantError:
                raise
            except AE200Error as exc:
                self.last_write_error = str(exc)
                raise HomeAssistantError(str(exc)) from exc

    async def async_set_attributes(
        self,
        group_id: str,
        attributes: Mapping[str, object],
    ) -> None:
        """Write and refresh exactly one group."""

        async with self._operation_lock:
            try:
                sent = await self.client.async_set_attributes(
                    group_id,
                    attributes,
                )
                await self._async_read_back_locked(group_id, sent)
            except AE200Error as exc:
                self.last_write_error = str(exc)
                raise HomeAssistantError(str(exc)) from exc

    def _status_for(self, group_id: str) -> Mapping[str, str]:
        if self.data is None:
            return {}
        return self.data.statuses.get(group_id, {})

    async def _async_read_back_locked(
        self,
        group_id: str,
        expected: Mapping[str, object],
    ) -> None:
        """Read back the target group and merge it into coordinator data."""

        attempts = self.verification_attempts if self.verify_writes else 1
        latest: Mapping[str, str] | None = None
        error: Exception | None = None

        for attempt in range(max(1, attempts)):
            if self.write_delay > 0:
                await asyncio.sleep(self.write_delay)

            try:
                result = await self.client.async_get_status([group_id])
                latest = result.statuses.get(group_id)
                error = None
            except AE200Error as exc:
                error = exc
                continue

            if latest is None:
                continue

            self._merge_group_status(
                group_id,
                latest,
                result.errors,
            )

            if not self.verify_writes:
                self.last_write_error = None
                return

            if all(
                values_match(key, value, latest.get(key, ""))
                for key, value in expected.items()
            ):
                self.last_write_error = None
                return

            _LOGGER.debug(
                "Write verification attempt %s/%s did not yet match for "
                "group %s. Expected %s, received %s",
                attempt + 1,
                attempts,
                group_id,
                expected,
                latest,
            )

        if error is not None:
            message = f"Unable to read back group {group_id}: {error}"
        else:
            message = (
                f"AE-200 did not confirm the requested values for group "
                f"{group_id}. Expected {dict(expected)}, received "
                f"{dict(latest or {})}"
            )
        self.last_write_error = message
        raise HomeAssistantError(message)

    def _merge_group_status(
        self,
        group_id: str,
        status: Mapping[str, str],
        errors: tuple[Mapping[str, str], ...],
    ) -> None:
        current_statuses = (
            dict(self.data.statuses) if self.data is not None else {}
        )
        current_statuses[group_id] = dict(status)

        current_groups = (
            dict(self.data.groups)
            if self.data is not None
            else dict(self.groups)
        )

        self.async_set_updated_data(
            AE200Data(
                groups=current_groups,
                statuses=current_statuses,
                protocol_errors=errors,
            )
        )
