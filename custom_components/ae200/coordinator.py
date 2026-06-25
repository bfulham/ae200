"""Data coordinator for Mitsubishi AE-200."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import time
from typing import Awaitable, Callable, Mapping, TypeVar

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_DRIVE,
    ATTR_MODE,
    CONF_FAILURE_GRACE,
    CONF_POLL_RETRIES,
    CONF_RETRY_DELAY,
    CONF_UPDATE_INTERVAL,
    CONF_VERIFY_ATTEMPTS,
    CONF_VERIFY_WRITES,
    CONF_WRITE_DELAY,
    DEFAULT_FAILURE_GRACE,
    DEFAULT_POLL_RETRIES,
    DEFAULT_RETRY_DELAY,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_VERIFY_ATTEMPTS,
    DEFAULT_VERIFY_WRITES,
    DEFAULT_WRITE_DELAY,
    DOMAIN,
)
from .models import AE200Data
from .protocol import (
    AE200Client,
    AE200Error,
    AE200Group,
    values_match,
)

_LOGGER = logging.getLogger(__name__)

REDISCOVERY_SECONDS = 30 * 60
REDISCOVERY_RETRY_SECONDS = 5 * 60

_T = TypeVar("_T")


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
        self.last_poll_error: str | None = None
        self.consecutive_poll_failures = 0
        self.using_stale_data = False

        update_interval = int(
            entry.options.get(
                CONF_UPDATE_INTERVAL,
                DEFAULT_UPDATE_INTERVAL,
            )
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
            self.entry.options.get(
                CONF_VERIFY_WRITES,
                DEFAULT_VERIFY_WRITES,
            )
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
            self.entry.options.get(
                CONF_WRITE_DELAY,
                DEFAULT_WRITE_DELAY,
            )
        )

    @property
    def poll_retries(self) -> int:
        return int(
            self.entry.options.get(
                CONF_POLL_RETRIES,
                DEFAULT_POLL_RETRIES,
            )
        )

    @property
    def retry_delay(self) -> float:
        return float(
            self.entry.options.get(
                CONF_RETRY_DELAY,
                DEFAULT_RETRY_DELAY,
            )
        )

    @property
    def failure_grace(self) -> int:
        return int(
            self.entry.options.get(
                CONF_FAILURE_GRACE,
                DEFAULT_FAILURE_GRACE,
            )
        )

    async def _async_retry(
        self,
        operation: Callable[[], Awaitable[_T]],
        description: str,
    ) -> _T:
        """Run a controller operation with bounded retries."""

        attempts = max(1, self.poll_retries + 1)
        last_error: AE200Error | None = None

        for attempt in range(attempts):
            try:
                return await operation()
            except asyncio.CancelledError:
                raise
            except AE200Error as exc:
                last_error = exc
                if attempt + 1 >= attempts:
                    break

                delay = self.retry_delay * (attempt + 1)
                _LOGGER.debug(
                    "AE-200 %s failed on attempt %s/%s: %s; "
                    "retrying in %.2f seconds",
                    description,
                    attempt + 1,
                    attempts,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

        assert last_error is not None
        raise last_error

    async def _async_update_data(self) -> AE200Data:
        """Fetch all group states while tolerating brief controller dropouts."""

        try:
            async with self._operation_lock:
                await self._async_refresh_groups_if_due()
                result = await self._async_retry(
                    lambda: self.client.async_get_status(self.groups),
                    "status poll",
                )
        except AE200Error as exc:
            return self._handle_poll_failure(exc)

        previous_statuses = (
            dict(self.data.statuses)
            if self.data is not None
            else {}
        )
        statuses = {
            group_id: dict(status)
            for group_id, status in result.statuses.items()
        }

        missing_groups = set(self.groups) - set(statuses)
        stale_groups: set[str] = set()

        # A partial AE-200 response should not erase otherwise valid
        # entities. Preserve the previous value only for groups omitted
        # from this poll and flag those groups as stale in diagnostics.
        for group_id in missing_groups:
            previous = previous_statuses.get(group_id)
            if previous is not None:
                statuses[group_id] = dict(previous)
                stale_groups.add(group_id)

        if self.consecutive_poll_failures:
            _LOGGER.info(
                "AE-200 communication recovered after %s failed poll(s)",
                self.consecutive_poll_failures,
            )

        self.consecutive_poll_failures = 0
        self.last_poll_error = None
        self.using_stale_data = bool(stale_groups)

        if result.errors:
            _LOGGER.debug(
                "AE-200 returned protocol warnings: %s",
                result.errors,
            )

        return AE200Data(
            groups=dict(self.groups),
            statuses=statuses,
            protocol_errors=result.errors,
            stale_groups=frozenset(stale_groups),
            using_stale_data=bool(stale_groups),
            consecutive_poll_failures=0,
            last_poll_error=None,
        )

    async def _async_refresh_groups_if_due(self) -> None:
        """Rediscover groups without letting a transient failure stop polling."""

        now = time.monotonic()
        if (
            self.groups
            and now - self._last_discovery < REDISCOVERY_SECONDS
        ):
            return

        try:
            discovered = await self._async_retry(
                self.client.async_discover_groups,
                "group discovery",
            )
        except AE200Error:
            if not self.groups:
                raise

            # Keep the known group list and retry discovery in five
            # minutes. Normal status polling can continue meanwhile.
            self._last_discovery = (
                now
                - REDISCOVERY_SECONDS
                + REDISCOVERY_RETRY_SECONDS
            )
            _LOGGER.warning(
                "AE-200 group rediscovery failed; continuing with the "
                "existing %s group(s)",
                len(self.groups),
            )
            return

        self.groups = dict(discovered)
        self._last_discovery = now

    def _handle_poll_failure(self, exc: AE200Error) -> AE200Data:
        """Keep the last good data during a short communication outage."""

        self.consecutive_poll_failures += 1
        self.last_poll_error = str(exc)

        can_use_cache = (
            self.data is not None
            and bool(self.data.statuses)
            and self.consecutive_poll_failures <= self.failure_grace
        )

        if can_use_cache:
            self.using_stale_data = True
            if self.consecutive_poll_failures == 1:
                _LOGGER.warning(
                    "AE-200 poll failed; retaining the last good state "
                    "for up to %s failed poll(s): %s",
                    self.failure_grace,
                    exc,
                )
            else:
                _LOGGER.debug(
                    "AE-200 poll failure %s/%s; retaining cached state: %s",
                    self.consecutive_poll_failures,
                    self.failure_grace,
                    exc,
                )

            return AE200Data(
                groups=dict(self.data.groups),
                statuses={
                    group_id: dict(status)
                    for group_id, status in self.data.statuses.items()
                },
                protocol_errors=self.data.protocol_errors,
                stale_groups=frozenset(self.data.statuses),
                using_stale_data=True,
                consecutive_poll_failures=self.consecutive_poll_failures,
                last_poll_error=str(exc),
            )

        self.using_stale_data = False
        raise UpdateFailed(
            "AE-200 communication failed "
            f"{self.consecutive_poll_failures} consecutive time(s): {exc}"
        ) from exc

    async def async_force_rediscovery(self) -> None:
        """Rediscover groups on the next refresh."""

        self._last_discovery = 0.0
        await self.async_request_refresh()

    async def async_set_hvac_mode(
        self,
        group_id: str,
        raw_mode: str | None,
    ) -> None:
        """Set power/mode for exactly one group."""

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

                await self._async_read_back_locked(
                    group_id,
                    expected,
                )
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
            except HomeAssistantError:
                raise
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
        current_stale = (
            set(self.data.stale_groups)
            if self.data is not None
            else set()
        )
        current_stale.discard(group_id)

        self.async_set_updated_data(
            AE200Data(
                groups=current_groups,
                statuses=current_statuses,
                protocol_errors=errors,
                stale_groups=frozenset(current_stale),
                using_stale_data=bool(current_stale),
                consecutive_poll_failures=0,
                last_poll_error=None,
            )
        )
