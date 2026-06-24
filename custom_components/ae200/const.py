"""Constants for the Mitsubishi AE-200 integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "ae200"
NAME: Final = "Mitsubishi AE-200"

CONF_NAME: Final = "name"
CONF_UPDATE_INTERVAL: Final = "update_interval"
CONF_TIMEOUT: Final = "timeout"
CONF_VERIFY_WRITES: Final = "verify_writes"
CONF_VERIFY_ATTEMPTS: Final = "verify_attempts"
CONF_WRITE_DELAY: Final = "write_delay"
CONF_MIN_TEMP: Final = "minimum_temperature"
CONF_MAX_TEMP: Final = "maximum_temperature"
CONF_ENABLE_SWING_CONTROL: Final = "enable_swing_control"
CONF_ENABLE_DRY_MODE: Final = "enable_dry_mode"
CONF_ENABLE_FAN_ONLY_MODE: Final = "enable_fan_only_mode"

DEFAULT_NAME: Final = "AE-200"
DEFAULT_UPDATE_INTERVAL: Final = 15
DEFAULT_TIMEOUT: Final = 8
DEFAULT_VERIFY_WRITES: Final = True
DEFAULT_VERIFY_ATTEMPTS: Final = 3
DEFAULT_WRITE_DELAY: Final = 1.0
DEFAULT_MIN_TEMP: Final = 16.0
DEFAULT_MAX_TEMP: Final = 30.0
DEFAULT_ENABLE_SWING_CONTROL: Final = True
DEFAULT_ENABLE_DRY_MODE: Final = False
DEFAULT_ENABLE_FAN_ONLY_MODE: Final = False

MIN_UPDATE_INTERVAL: Final = 5
MAX_UPDATE_INTERVAL: Final = 300

MANUFACTURER: Final = "Mitsubishi Electric"
CONTROLLER_MODEL: Final = "AE-200"
INDOOR_UNIT_MODEL: Final = "AE-200 controlled air-conditioning group"

ATTR_DRIVE: Final = "Drive"
ATTR_MODE: Final = "Mode"
ATTR_MODE_STATUS: Final = "ModeStatus"
ATTR_SET_TEMP: Final = "SetTemp"
ATTR_INLET_TEMP: Final = "InletTemp"
ATTR_INLET_HUMIDITY: Final = "InletHumidity"
ATTR_AIR_DIRECTION: Final = "AirDirection"
ATTR_FAN_SPEED: Final = "FanSpeed"
ATTR_REMOTE_CONTROL: Final = "RemoCon"
ATTR_FILTER_SIGN: Final = "FilterSign"
ATTR_HOLD: Final = "Hold"
ATTR_ENERGY_CONTROL: Final = "EnergyControl"
ATTR_SCHEDULE: Final = "Schedule"
ATTR_SCHEDULE_AVAILABLE: Final = "ScheduleAvail"
ATTR_ERROR_SIGN: Final = "ErrorSign"
ATTR_CHECK_WATER: Final = "CheckWater"
ATTR_COOL_MIN: Final = "CoolMin"
ATTR_COOL_MAX: Final = "CoolMax"
ATTR_HEAT_MIN: Final = "HeatMin"
ATTR_HEAT_MAX: Final = "HeatMax"
ATTR_AUTO_MIN: Final = "AutoMin"
ATTR_AUTO_MAX: Final = "AutoMax"
ATTR_OCCUPANCY: Final = "Occupancy"
ATTR_OUTDOOR_TEMP: Final = "OutdoorTemp"

# These attributes were accepted by the supplied AE-200 dump. Deliberately
# excluded: DriveStatus, SetTempStatus, AirDirectionStatus,
# AirDirectionItem, FanSpeedStatus and ErrorCode. That controller returned
# Unknown Attribute (0101) for those names.
STATUS_ATTRIBUTES: Final[tuple[str, ...]] = (
    ATTR_DRIVE,
    ATTR_MODE,
    ATTR_MODE_STATUS,
    ATTR_SET_TEMP,
    ATTR_INLET_TEMP,
    ATTR_INLET_HUMIDITY,
    ATTR_AIR_DIRECTION,
    ATTR_FAN_SPEED,
    ATTR_REMOTE_CONTROL,
    "DriveItem",
    "ModeItem",
    "SetTempItem",
    "FanSpeedItem",
    ATTR_FILTER_SIGN,
    ATTR_HOLD,
    ATTR_ENERGY_CONTROL,
    ATTR_SCHEDULE,
    ATTR_SCHEDULE_AVAILABLE,
    ATTR_ERROR_SIGN,
    ATTR_CHECK_WATER,
    ATTR_COOL_MIN,
    ATTR_COOL_MAX,
    ATTR_HEAT_MIN,
    ATTR_HEAT_MAX,
    ATTR_AUTO_MIN,
    ATTR_AUTO_MAX,
    ATTR_OCCUPANCY,
    ATTR_OUTDOOR_TEMP,
)

WRITABLE_ATTRIBUTES: Final[frozenset[str]] = frozenset(
    {
        ATTR_DRIVE,
        ATTR_MODE,
        ATTR_SET_TEMP,
        ATTR_FAN_SPEED,
        ATTR_AIR_DIRECTION,
    }
)

RAW_MODE_AUTO: Final = "AUTO"
RAW_MODE_AUTO_COOL: Final = "AUTOCOOL"
RAW_MODE_AUTO_HEAT: Final = "AUTOHEAT"
RAW_MODE_COOL: Final = "COOL"
RAW_MODE_HEAT: Final = "HEAT"
RAW_MODE_DRY: Final = "DRY"
RAW_MODE_FAN: Final = "FAN"

AUTO_RAW_MODES: Final[frozenset[str]] = frozenset(
    {RAW_MODE_AUTO, RAW_MODE_AUTO_COOL, RAW_MODE_AUTO_HEAT}
)

KNOWN_FAN_MODES: Final[tuple[str, ...]] = (
    "AUTO",
    "LOW",
    "MID1",
    "MID2",
    "HIGH",
)

KNOWN_AIR_DIRECTIONS: Final[tuple[str, ...]] = (
    "HORIZONTAL",
    "VERTICAL",
    "SWING",
)

PLATFORMS: Final[tuple[str, ...]] = (
    "climate",
    "sensor",
    "binary_sensor",
    "button",
)
