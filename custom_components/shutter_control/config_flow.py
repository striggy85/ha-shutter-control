"""Config flow for Shutter Control."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AUTO_DOWN_ENABLED,
    CONF_AUTO_UP_ENABLED,
    CONF_AZIMUTH_END,
    CONF_AZIMUTH_START,
    CONF_CLOSED_POSITION,
    CONF_CLOUD_SENSOR,
    CONF_CLOUD_THRESHOLD,
    CONF_COVER_ENTITY,
    CONF_DOWN_EARLIEST,
    CONF_DOWN_LATEST,
    CONF_DOWN_OFFSET,
    CONF_DOWN_TIME,
    CONF_DOWN_TIME_WEEKEND,
    CONF_DOWN_TRIGGER,
    CONF_ELEVATION_MAX,
    CONF_ELEVATION_MIN,
    CONF_NAME,
    CONF_OPEN_POSITION,
    CONF_ROOM_TYPE,
    CONF_SHADE_ENABLED,
    CONF_SHADE_ONLY_LOWER,
    CONF_SHADE_POSITION,
    CONF_SUN_ENTITY,
    CONF_TEMP_SENSOR,
    CONF_TEMP_THRESHOLD,
    CONF_UP_EARLIEST,
    CONF_UP_LATEST,
    CONF_UP_OFFSET,
    CONF_UP_TIME,
    CONF_UP_TIME_WEEKEND,
    CONF_UP_TRIGGER,
    CONF_UPDATE_INTERVAL,
    DEFAULT_AZIMUTH_END,
    DEFAULT_AZIMUTH_START,
    DEFAULT_CLOSED_POSITION,
    DEFAULT_CLOUD_THRESHOLD,
    DEFAULT_DOWN_OFFSET,
    DEFAULT_DOWN_TIME,
    DEFAULT_DOWN_TIME_WEEKEND,
    DEFAULT_DOWN_TRIGGER,
    DEFAULT_ELEVATION_MAX,
    DEFAULT_ELEVATION_MIN,
    DEFAULT_OPEN_POSITION,
    DEFAULT_ROOM_TYPE,
    DEFAULT_SHADE_ONLY_LOWER,
    DEFAULT_SHADE_POSITION,
    DEFAULT_SUN_ENTITY,
    DEFAULT_TEMP_THRESHOLD,
    DEFAULT_UP_OFFSET,
    DEFAULT_UP_TIME,
    DEFAULT_UP_TIME_WEEKEND,
    DEFAULT_UP_TRIGGER,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    DOWN_TRIGGERS,
    ROOM_TYPES,
    SUBENTRY_TYPE_COVER,
    UP_TRIGGERS,
)


def _num(
    min_: float,
    max_: float,
    step: float,
    unit: str,
    mode: selector.NumberSelectorMode = selector.NumberSelectorMode.BOX,
) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=min_, max=max_, step=step, unit_of_measurement=unit, mode=mode
        )
    )


def _inherit(
    schema: dict,
    key: str,
    sel,
    *,
    defaults: dict[str, Any],
    fallback: Any,
    glob: bool,
) -> None:
    """Add an inheritable field.

    Global mode -> required with a concrete default. Per-group mode -> optional
    override (empty means "use the global value").
    """
    if glob:
        schema[vol.Required(key, default=defaults.get(key, fallback))] = sel
    else:
        schema[
            vol.Optional(key, description={"suggested_value": defaults.get(key)})
        ] = sel


def _azimuth_fields(schema: dict, defaults: dict[str, Any], glob: bool) -> None:
    _inherit(schema, CONF_AZIMUTH_START, _num(0, 360, 1, "°"),
             defaults=defaults, fallback=DEFAULT_AZIMUTH_START, glob=glob)
    _inherit(schema, CONF_AZIMUTH_END, _num(0, 360, 1, "°"),
             defaults=defaults, fallback=DEFAULT_AZIMUTH_END, glob=glob)


def _elevation_fields(schema: dict, defaults: dict[str, Any], glob: bool) -> None:
    _inherit(schema, CONF_ELEVATION_MIN, _num(0, 90, 1, "°"),
             defaults=defaults, fallback=DEFAULT_ELEVATION_MIN, glob=glob)
    _inherit(schema, CONF_ELEVATION_MAX, _num(0, 90, 1, "°"),
             defaults=defaults, fallback=DEFAULT_ELEVATION_MAX, glob=glob)


def _trigger_sel(options: list[str]) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            translation_key="trigger",
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _up_timing_fields(schema: dict, defaults: dict[str, Any], glob: bool) -> None:
    _inherit(schema, CONF_UP_TRIGGER, _trigger_sel(UP_TRIGGERS),
             defaults=defaults, fallback=DEFAULT_UP_TRIGGER, glob=glob)
    _inherit(schema, CONF_UP_TIME, selector.TimeSelector(),
             defaults=defaults, fallback=DEFAULT_UP_TIME, glob=glob)
    _inherit(schema, CONF_UP_TIME_WEEKEND, selector.TimeSelector(),
             defaults=defaults, fallback=DEFAULT_UP_TIME_WEEKEND, glob=glob)
    _inherit(schema, CONF_UP_OFFSET, _num(-180, 180, 5, "min"),
             defaults=defaults, fallback=DEFAULT_UP_OFFSET, glob=glob)
    schema[vol.Optional(CONF_UP_EARLIEST,
           description={"suggested_value": defaults.get(CONF_UP_EARLIEST)})] = \
        selector.TimeSelector()
    schema[vol.Optional(CONF_UP_LATEST,
           description={"suggested_value": defaults.get(CONF_UP_LATEST)})] = \
        selector.TimeSelector()


def _down_timing_fields(schema: dict, defaults: dict[str, Any], glob: bool) -> None:
    _inherit(schema, CONF_DOWN_TRIGGER, _trigger_sel(DOWN_TRIGGERS),
             defaults=defaults, fallback=DEFAULT_DOWN_TRIGGER, glob=glob)
    _inherit(schema, CONF_DOWN_TIME, selector.TimeSelector(),
             defaults=defaults, fallback=DEFAULT_DOWN_TIME, glob=glob)
    _inherit(schema, CONF_DOWN_TIME_WEEKEND, selector.TimeSelector(),
             defaults=defaults, fallback=DEFAULT_DOWN_TIME_WEEKEND, glob=glob)
    _inherit(schema, CONF_DOWN_OFFSET, _num(-180, 180, 5, "min"),
             defaults=defaults, fallback=DEFAULT_DOWN_OFFSET, glob=glob)
    schema[vol.Optional(CONF_DOWN_EARLIEST,
           description={"suggested_value": defaults.get(CONF_DOWN_EARLIEST)})] = \
        selector.TimeSelector()
    schema[vol.Optional(CONF_DOWN_LATEST,
           description={"suggested_value": defaults.get(CONF_DOWN_LATEST)})] = \
        selector.TimeSelector()


def _global_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Schema for the global options (sensors, thresholds + inheritable defaults)."""
    schema: dict = {
        vol.Required(
            CONF_SUN_ENTITY,
            default=defaults.get(CONF_SUN_ENTITY, DEFAULT_SUN_ENTITY),
        ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sun")),
        vol.Optional(
            CONF_CLOUD_SENSOR,
            description={"suggested_value": defaults.get(CONF_CLOUD_SENSOR)},
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["sensor", "weather"])
        ),
        vol.Optional(
            CONF_CLOUD_THRESHOLD,
            default=defaults.get(CONF_CLOUD_THRESHOLD, DEFAULT_CLOUD_THRESHOLD),
        ): _num(0, 100, 1, "%"),
        vol.Optional(
            CONF_TEMP_SENSOR,
            description={"suggested_value": defaults.get(CONF_TEMP_SENSOR)},
        ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        vol.Optional(
            CONF_TEMP_THRESHOLD,
            default=defaults.get(CONF_TEMP_THRESHOLD, DEFAULT_TEMP_THRESHOLD),
        ): _num(-20, 50, 0.5, "°C"),
        vol.Optional(
            CONF_UPDATE_INTERVAL,
            default=defaults.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        ): _num(15, 900, 5, "s"),
        vol.Optional(
            CONF_SHADE_ONLY_LOWER,
            default=defaults.get(CONF_SHADE_ONLY_LOWER, DEFAULT_SHADE_ONLY_LOWER),
        ): selector.BooleanSelector(),
    }
    # Inheritable defaults (overridable per group).
    _azimuth_fields(schema, defaults, glob=True)
    _elevation_fields(schema, defaults, glob=True)
    _up_timing_fields(schema, defaults, glob=True)
    _down_timing_fields(schema, defaults, glob=True)
    return vol.Schema(schema)


def _cover_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Schema for a room/group (subentry).

    Azimuth, elevation and the up/down timing fields are optional here: leave
    them empty to inherit the global default, or set a value to override it.
    Positions stay per group.
    """

    def d(key: str, fallback: Any) -> Any:
        return defaults.get(key, fallback)

    # Existing entries created before grouping stored a single entity id as a
    # string; normalise to a list so the multi-select prefills correctly.
    covers_default = defaults.get(CONF_COVER_ENTITY)
    if isinstance(covers_default, str):
        covers_default = [covers_default]

    schema: dict = {
        vol.Required(CONF_NAME, default=d(CONF_NAME, "")): selector.TextSelector(),
        vol.Required(
            CONF_COVER_ENTITY,
            description={"suggested_value": covers_default},
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="cover", multiple=True)
        ),
        vol.Required(
            CONF_ROOM_TYPE, default=d(CONF_ROOM_TYPE, DEFAULT_ROOM_TYPE)
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=ROOM_TYPES,
                translation_key="room_type",
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(
            CONF_SHADE_ENABLED, default=d(CONF_SHADE_ENABLED, True)
        ): selector.BooleanSelector(),
    }
    # Shading window: inherited overrides.
    _azimuth_fields(schema, defaults, glob=False)
    _elevation_fields(schema, defaults, glob=False)
    # Positions stay per group.
    schema[
        vol.Required(
            CONF_SHADE_POSITION, default=d(CONF_SHADE_POSITION, DEFAULT_SHADE_POSITION)
        )
    ] = _num(0, 100, 1, "%", selector.NumberSelectorMode.SLIDER)
    schema[
        vol.Required(
            CONF_OPEN_POSITION, default=d(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION)
        )
    ] = _num(0, 100, 1, "%", selector.NumberSelectorMode.SLIDER)
    schema[
        vol.Required(
            CONF_CLOSED_POSITION, default=d(CONF_CLOSED_POSITION, DEFAULT_CLOSED_POSITION)
        )
    ] = _num(0, 100, 1, "%", selector.NumberSelectorMode.SLIDER)
    # Auto up (morning): enable toggle per group + inherited timing.
    schema[
        vol.Required(CONF_AUTO_UP_ENABLED, default=d(CONF_AUTO_UP_ENABLED, True))
    ] = selector.BooleanSelector()
    _up_timing_fields(schema, defaults, glob=False)
    # Auto down (evening): enable toggle per group + inherited timing.
    schema[
        vol.Required(CONF_AUTO_DOWN_ENABLED, default=d(CONF_AUTO_DOWN_ENABLED, True))
    ] = selector.BooleanSelector()
    _down_timing_fields(schema, defaults, glob=False)
    return vol.Schema(schema)


class ShutterControlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the main config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        # Single hub instance is enough; covers are added as subentries.
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="Shutter Control", data={}, options=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=_global_schema({})
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ShutterControlOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_TYPE_COVER: CoverSubentryFlow}


class ShutterControlOptionsFlow(OptionsFlow):
    """Edit the global options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=_global_schema(dict(self.config_entry.options)),
        )


class CoverSubentryFlow(ConfigSubentryFlow):
    """Add / reconfigure a managed cover."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME], data=user_input
            )
        return self.async_show_form(
            step_id="user", data_schema=_cover_schema({})
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                title=user_input[CONF_NAME],
                data=user_input,
            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_cover_schema(dict(subentry.data)),
        )
