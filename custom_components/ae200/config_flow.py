"""Config flow for Mitsubishi AE-200."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import (
    CONF_ENABLE_DRY_MODE,
    CONF_ENABLE_FAN_ONLY_MODE,
    CONF_ENABLE_SWING_CONTROL,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_NAME,
    CONF_TIMEOUT,
    CONF_UPDATE_INTERVAL,
    CONF_VERIFY_ATTEMPTS,
    CONF_VERIFY_WRITES,
    CONF_WRITE_DELAY,
    DEFAULT_ENABLE_DRY_MODE,
    DEFAULT_ENABLE_FAN_ONLY_MODE,
    DEFAULT_ENABLE_SWING_CONTROL,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_VERIFY_ATTEMPTS,
    DEFAULT_VERIFY_WRITES,
    DEFAULT_WRITE_DELAY,
    DOMAIN,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
)
from .protocol import (
    AE200Client,
    AE200Error,
    clean_host,
)


class CannotConnect(Exception):
    """Raised when validation cannot connect."""


async def _validate_host(
    hass: HomeAssistant,
    host: str,
    timeout: float,
) -> tuple[str, int]:
    """Connect, discover groups and verify a status request."""

    clean = clean_host(host)
    client = AE200Client(
        clean,
        async_get_clientsession(hass),
        timeout=timeout,
    )
    try:
        groups = await client.async_discover_groups()
        result = await client.async_get_status(groups)
    except AE200Error as exc:
        raise CannotConnect from exc

    if not result.statuses:
        raise CannotConnect
    return clean, len(groups)


class AE200ConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Handle an AE-200 config flow."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle user setup."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                host, group_count = await _validate_host(
                    self.hass,
                    user_input[CONF_HOST],
                    DEFAULT_TIMEOUT,
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                self._async_abort_entries_match({CONF_HOST: host})
                name = user_input.get(CONF_NAME, DEFAULT_NAME).strip()
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_HOST: host,
                        CONF_NAME: name,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST,
                    default=(user_input or {}).get(CONF_HOST, ""),
                ): cv.string,
                vol.Required(
                    CONF_NAME,
                    default=(user_input or {}).get(
                        CONF_NAME,
                        DEFAULT_NAME,
                    ),
                ): cv.string,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Allow the controller host to be changed from the UI."""

        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                host, _group_count = await _validate_host(
                    self.hass,
                    user_input[CONF_HOST],
                    float(
                        entry.options.get(
                            CONF_TIMEOUT,
                            DEFAULT_TIMEOUT,
                        )
                    ),
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                duplicate = next(
                    (
                        configured
                        for configured in self._async_current_entries()
                        if configured.entry_id != entry.entry_id
                        and configured.data.get(CONF_HOST) == host
                    ),
                    None,
                )
                if duplicate is not None:
                    return self.async_abort(reason="already_configured")

                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_HOST: host},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=entry.data[CONF_HOST],
                    ): cv.string,
                }
            ),
            errors=errors,
        )

    async def async_step_import(
        self,
        import_data: dict[str, Any],
    ) -> config_entries.ConfigFlowResult:
        """Import the original YAML platform configuration."""

        host = (
            import_data.get(CONF_HOST)
            or import_data.get("ip_address")
            or ""
        )
        name = (
            import_data.get(CONF_NAME)
            or import_data.get("controller_id")
            or DEFAULT_NAME
        )
        try:
            clean = clean_host(host)
        except AE200Error:
            return self.async_abort(reason="cannot_connect")

        self._async_abort_entries_match({CONF_HOST: clean})

        return self.async_create_entry(
            title=str(name),
            data={
                CONF_HOST: clean,
                CONF_NAME: str(name),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""

        return AE200OptionsFlow(config_entry)


class AE200OptionsFlow(config_entries.OptionsFlow):
    """Configure polling, verification and optional features."""

    def __init__(
        self,
        config_entry: config_entries.ConfigEntry,
    ) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage integration options."""

        if user_input is not None:
            if (
                float(user_input[CONF_MIN_TEMP])
                >= float(user_input[CONF_MAX_TEMP])
            ):
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._schema(user_input),
                    errors={"base": "invalid_temperature_range"},
                )
            return self.async_create_entry(
                title="",
                data=user_input,
            )

        return self.async_show_form(
            step_id="init",
            data_schema=self._schema(self._config_entry.options),
        )

    def _schema(
        self,
        values: dict[str, Any],
    ) -> vol.Schema:
        def current(key: str, default: Any) -> Any:
            return values.get(key, default)

        return vol.Schema(
            {
                vol.Required(
                    CONF_UPDATE_INTERVAL,
                    default=current(
                        CONF_UPDATE_INTERVAL,
                        DEFAULT_UPDATE_INTERVAL,
                    ),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(
                        min=MIN_UPDATE_INTERVAL,
                        max=MAX_UPDATE_INTERVAL,
                    ),
                ),
                vol.Required(
                    CONF_TIMEOUT,
                    default=current(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=2, max=60),
                ),
                vol.Required(
                    CONF_VERIFY_WRITES,
                    default=current(
                        CONF_VERIFY_WRITES,
                        DEFAULT_VERIFY_WRITES,
                    ),
                ): cv.boolean,
                vol.Required(
                    CONF_VERIFY_ATTEMPTS,
                    default=current(
                        CONF_VERIFY_ATTEMPTS,
                        DEFAULT_VERIFY_ATTEMPTS,
                    ),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=1, max=10),
                ),
                vol.Required(
                    CONF_WRITE_DELAY,
                    default=current(
                        CONF_WRITE_DELAY,
                        DEFAULT_WRITE_DELAY,
                    ),
                ): vol.All(
                    vol.Coerce(float),
                    vol.Range(min=0.1, max=10.0),
                ),
                vol.Required(
                    CONF_MIN_TEMP,
                    default=current(
                        CONF_MIN_TEMP,
                        DEFAULT_MIN_TEMP,
                    ),
                ): vol.All(
                    vol.Coerce(float),
                    vol.Range(min=5.0, max=35.0),
                ),
                vol.Required(
                    CONF_MAX_TEMP,
                    default=current(
                        CONF_MAX_TEMP,
                        DEFAULT_MAX_TEMP,
                    ),
                ): vol.All(
                    vol.Coerce(float),
                    vol.Range(min=10.0, max=40.0),
                ),
                vol.Required(
                    CONF_ENABLE_SWING_CONTROL,
                    default=current(
                        CONF_ENABLE_SWING_CONTROL,
                        DEFAULT_ENABLE_SWING_CONTROL,
                    ),
                ): cv.boolean,
                vol.Required(
                    CONF_ENABLE_DRY_MODE,
                    default=current(
                        CONF_ENABLE_DRY_MODE,
                        DEFAULT_ENABLE_DRY_MODE,
                    ),
                ): cv.boolean,
                vol.Required(
                    CONF_ENABLE_FAN_ONLY_MODE,
                    default=current(
                        CONF_ENABLE_FAN_ONLY_MODE,
                        DEFAULT_ENABLE_FAN_ONLY_MODE,
                    ),
                ): cv.boolean,
            }
        )
