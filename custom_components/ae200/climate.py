"""Climate platform for Mitsubishi AE-200."""

from __future__ import annotations

from typing import Any, Mapping

from homeassistant.components.climate import (
    PLATFORM_SCHEMA,
    ClimateEntity,
)
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import (
    ATTR_AIR_DIRECTION,
    ATTR_AUTO_MAX,
    ATTR_AUTO_MIN,
    ATTR_CHECK_WATER,
    ATTR_COOL_MAX,
    ATTR_COOL_MIN,
    ATTR_DRIVE,
    ATTR_ENERGY_CONTROL,
    ATTR_ERROR_SIGN,
    ATTR_FAN_SPEED,
    ATTR_FILTER_SIGN,
    ATTR_HEAT_MAX,
    ATTR_HEAT_MIN,
    ATTR_HOLD,
    ATTR_INLET_HUMIDITY,
    ATTR_INLET_TEMP,
    ATTR_MODE,
    ATTR_MODE_STATUS,
    ATTR_REMOTE_CONTROL,
    ATTR_SCHEDULE,
    ATTR_SET_TEMP,
    AUTO_RAW_MODES,
    CONF_ENABLE_DRY_MODE,
    CONF_ENABLE_FAN_ONLY_MODE,
    CONF_ENABLE_SWING_CONTROL,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_NAME,
    DEFAULT_ENABLE_DRY_MODE,
    DEFAULT_ENABLE_FAN_ONLY_MODE,
    DEFAULT_ENABLE_SWING_CONTROL,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN,
    KNOWN_AIR_DIRECTIONS,
    KNOWN_FAN_MODES,
    RAW_MODE_AUTO,
    RAW_MODE_AUTO_COOL,
    RAW_MODE_AUTO_HEAT,
    RAW_MODE_COOL,
    RAW_MODE_DRY,
    RAW_MODE_FAN,
    RAW_MODE_HEAT,
)
from .entity import AE200GroupEntity
from .models import as_float
from .protocol import values_match

CONF_CONTROLLER_ID = "controller_id"
CONF_LEGACY_IP_ADDRESS = "ip_address"
PARALLEL_UPDATES = 1

# Compatibility path for the original integration's YAML configuration.
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_LEGACY_IP_ADDRESS): cv.string,
        vol.Optional(CONF_CONTROLLER_ID, default="AE-200"): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Import the legacy YAML platform into a config entry."""

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data={
                "ip_address": config[CONF_LEGACY_IP_ADDRESS],
                CONF_CONTROLLER_ID: config[CONF_CONTROLLER_ID],
            },
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up climate entities from a config entry."""

    coordinator = entry.runtime_data.coordinator
    known_groups: set[str] = set()

    @callback
    def async_add_new_groups() -> None:
        entities = []
        for group_id, group in coordinator.data.groups.items():
            if group_id in known_groups:
                continue
            known_groups.add(group_id)
            entities.append(
                AE200ClimateEntity(
                    coordinator,
                    entry.entry_id,
                    group,
                )
            )
        if entities:
            async_add_entities(entities)

    async_add_new_groups()
    entry.async_on_unload(
        coordinator.async_add_listener(async_add_new_groups)
    )


def _raw_to_hvac_mode(
    drive: str,
    raw_mode: str,
) -> HVACMode:
    if drive.upper() != "ON":
        return HVACMode.OFF

    mode = raw_mode.upper()
    if mode == RAW_MODE_HEAT:
        return HVACMode.HEAT
    if mode == RAW_MODE_COOL:
        return HVACMode.COOL
    if mode == RAW_MODE_DRY:
        return HVACMode.DRY
    if mode == RAW_MODE_FAN:
        return HVACMode.FAN_ONLY
    if mode in AUTO_RAW_MODES:
        return HVACMode.AUTO
    return HVACMode.AUTO


def _hvac_to_raw_mode(mode: HVACMode) -> str | None:
    if mode == HVACMode.OFF:
        return None
    if mode == HVACMode.HEAT:
        return RAW_MODE_HEAT
    if mode == HVACMode.COOL:
        return RAW_MODE_COOL
    if mode == HVACMode.AUTO:
        # AUTOCOOL/AUTOHEAT are read-back states. The controller is commanded
        # into automatic mode using the plain AUTO value.
        return RAW_MODE_AUTO
    if mode == HVACMode.DRY:
        return RAW_MODE_DRY
    if mode == HVACMode.FAN_ONLY:
        return RAW_MODE_FAN
    return None


class AE200ClimateEntity(AE200GroupEntity, ClimateEntity):
    """Climate entity for one AE-200 group."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_precision = 0.1
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        coordinator,
        entry_id: str,
        group,
    ) -> None:
        super().__init__(
            coordinator,
            entry_id,
            group,
            "climate",
        )

    @property
    def supported_features(self) -> ClimateEntityFeature:
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        if self.coordinator.entry.options.get(
            CONF_ENABLE_SWING_CONTROL,
            DEFAULT_ENABLE_SWING_CONTROL,
        ):
            features |= ClimateEntityFeature.SWING_MODE
        return features

    @property
    def current_temperature(self) -> float | None:
        return as_float(self.status.get(ATTR_INLET_TEMP))

    @property
    def current_humidity(self) -> float | None:
        humidity = as_float(self.status.get(ATTR_INLET_HUMIDITY))
        # The supplied controller returns 0 when no humidity sensor exists.
        return humidity if humidity is not None and humidity > 0 else None

    @property
    def target_temperature(self) -> float | None:
        return as_float(self.status.get(ATTR_SET_TEMP))

    @property
    def min_temp(self) -> float:
        raw_mode = self.status.get(ATTR_MODE, "").upper()
        key = ATTR_AUTO_MIN
        if raw_mode == RAW_MODE_HEAT:
            key = ATTR_HEAT_MIN
        elif raw_mode == RAW_MODE_COOL:
            key = ATTR_COOL_MIN

        reported = as_float(self.status.get(key))
        return reported if reported is not None else float(
            self.coordinator.entry.options.get(
                CONF_MIN_TEMP,
                DEFAULT_MIN_TEMP,
            )
        )

    @property
    def max_temp(self) -> float:
        raw_mode = self.status.get(ATTR_MODE, "").upper()
        key = ATTR_AUTO_MAX
        if raw_mode == RAW_MODE_HEAT:
            key = ATTR_HEAT_MAX
        elif raw_mode == RAW_MODE_COOL:
            key = ATTR_COOL_MAX

        reported = as_float(self.status.get(key))
        return reported if reported is not None else float(
            self.coordinator.entry.options.get(
                CONF_MAX_TEMP,
                DEFAULT_MAX_TEMP,
            )
        )

    @property
    def hvac_mode(self) -> HVACMode:
        return _raw_to_hvac_mode(
            self.status.get(ATTR_DRIVE, ""),
            self.status.get(ATTR_MODE, ""),
        )

    @property
    def hvac_modes(self) -> list[HVACMode]:
        modes = [
            HVACMode.OFF,
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.AUTO,
        ]
        raw_modes = (
            set(self.coordinator.data.raw_modes)
            if self.coordinator.data is not None
            else set()
        )
        if (
            RAW_MODE_DRY in raw_modes
            or self.coordinator.entry.options.get(
                CONF_ENABLE_DRY_MODE,
                DEFAULT_ENABLE_DRY_MODE,
            )
        ):
            modes.append(HVACMode.DRY)
        if (
            RAW_MODE_FAN in raw_modes
            or self.coordinator.entry.options.get(
                CONF_ENABLE_FAN_ONLY_MODE,
                DEFAULT_ENABLE_FAN_ONLY_MODE,
            )
        ):
            modes.append(HVACMode.FAN_ONLY)
        return modes

    @property
    def hvac_action(self) -> HVACAction:
        if self.status.get(ATTR_DRIVE, "").upper() != "ON":
            return HVACAction.OFF

        raw_mode = self.status.get(ATTR_MODE, "").upper()
        if raw_mode in {RAW_MODE_HEAT, RAW_MODE_AUTO_HEAT}:
            return HVACAction.HEATING
        if raw_mode in {RAW_MODE_COOL, RAW_MODE_AUTO_COOL}:
            return HVACAction.COOLING
        if raw_mode == RAW_MODE_DRY:
            return HVACAction.DRYING
        if raw_mode == RAW_MODE_FAN:
            return HVACAction.FAN
        return HVACAction.IDLE

    @property
    def fan_mode(self) -> str | None:
        value = self.status.get(ATTR_FAN_SPEED, "").upper()
        return value or None

    @property
    def fan_modes(self) -> list[str]:
        return list(KNOWN_FAN_MODES)

    @property
    def swing_mode(self) -> str | None:
        value = self.status.get(ATTR_AIR_DIRECTION, "").upper()
        return value or None

    @property
    def swing_modes(self) -> list[str]:
        return list(KNOWN_AIR_DIRECTIONS)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        return {
            "controller_group_id": self.group_id,
            "raw_mode": self.status.get(ATTR_MODE),
            "mode_control_status": self.status.get(ATTR_MODE_STATUS),
            "remote_control": self.status.get(ATTR_REMOTE_CONTROL),
            "filter_sign": self.status.get(ATTR_FILTER_SIGN),
            "error_sign": self.status.get(ATTR_ERROR_SIGN),
            "check_water": self.status.get(ATTR_CHECK_WATER),
            "schedule": self.status.get(ATTR_SCHEDULE),
            "hold": self.status.get(ATTR_HOLD),
            "energy_control": self.status.get(ATTR_ENERGY_CONTROL),
            "hvac_action_is_inferred": True,
        }

    async def async_set_hvac_mode(
        self,
        hvac_mode: HVACMode,
    ) -> None:
        raw_mode = _hvac_to_raw_mode(hvac_mode)
        await self.coordinator.async_set_hvac_mode(
            self.group_id,
            raw_mode,
        )

    async def async_turn_on(self) -> None:
        await self.coordinator.async_set_attributes(
            self.group_id,
            {ATTR_DRIVE: "ON"},
        )

    async def async_turn_off(self) -> None:
        await self.coordinator.async_set_attributes(
            self.group_id,
            {ATTR_DRIVE: "OFF"},
        )

    async def async_set_temperature(
        self,
        **kwargs: Any,
    ) -> None:
        requested_mode = kwargs.get("hvac_mode")
        if requested_mode is not None:
            await self.async_set_hvac_mode(requested_mode)

        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        value = float(temperature)
        if value < self.min_temp or value > self.max_temp:
            raise HomeAssistantError(
                f"Temperature {value:g} °C is outside this group's "
                f"{self.min_temp:g}–{self.max_temp:g} °C range"
            )

        await self.coordinator.async_set_attributes(
            self.group_id,
            {ATTR_SET_TEMP: value},
        )

    async def async_set_fan_mode(
        self,
        fan_mode: str,
    ) -> None:
        await self.coordinator.async_set_attributes(
            self.group_id,
            {ATTR_FAN_SPEED: fan_mode},
        )

    async def async_set_swing_mode(
        self,
        swing_mode: str,
    ) -> None:
        await self.coordinator.async_set_attributes(
            self.group_id,
            {ATTR_AIR_DIRECTION: swing_mode},
        )
