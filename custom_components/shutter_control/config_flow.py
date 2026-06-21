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
    CONF_BRIGHTNESS_SENSOR,
    CONF_BRIGHTNESS_THRESHOLD,
    CONF_CLOSED_POSITION,
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
    DEFAULT_BRIGHTNESS_THRESHOLD,
    DEFAULT_CLOSED_POSITION,
    DEFAULT_DOWN_OFFSET,
    DEFAULT_DOWN_TIME,
    DEFAULT_DOWN_TIME_WEEKEND,
    DEFAULT_DOWN_TRIGGER,
    DEFAULT_ELEVATION_MAX,
    DEFAULT_ELEVATION_MIN,
    DEFAULT_OPEN_POSITION,
    DEFAULT_ROOM_TYPE,
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


def _global_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Schema for the global options."""
    return vol.Schema(
        {
            vol.Required(
                CONF_SUN_ENTITY,
                default=defaults.get(CONF_SUN_ENTITY, DEFAULT_SUN_ENTITY),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sun")
            ),
            vol.Optional(
                CONF_BRIGHTNESS_SENSOR,
                description={
                    "suggested_value": defaults.get(CONF_BRIGHTNESS_SENSOR)
                },
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(
                CONF_BRIGHTNESS_THRESHOLD,
                default=defaults.get(
                    CONF_BRIGHTNESS_THRESHOLD, DEFAULT_BRIGHTNESS_THRESHOLD
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=150000, step=500, unit_of_measurement="lx",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_TEMP_SENSOR,
                description={"suggested_value": defaults.get(CONF_TEMP_SENSOR)},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(
                CONF_TEMP_THRESHOLD,
                default=defaults.get(CONF_TEMP_THRESHOLD, DEFAULT_TEMP_THRESHOLD),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-20, max=50, step=0.5, unit_of_measurement="°C",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_UPDATE_INTERVAL,
                default=defaults.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=15, max=900, step=5, unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


def _cover_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Schema for a single managed cover (subentry)."""

    def d(key: str, fallback: Any) -> Any:
        return defaults.get(key, fallback)

    # Existing entries created before grouping stored a single entity id as a
    # string; normalise to a list so the multi-select prefills correctly.
    covers_default = defaults.get(CONF_COVER_ENTITY)
    if isinstance(covers_default, str):
        covers_default = [covers_default]

    return vol.Schema(
        {
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
            # --- Shading ---
            vol.Required(
                CONF_SHADE_ENABLED, default=d(CONF_SHADE_ENABLED, True)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_AZIMUTH_START, default=d(CONF_AZIMUTH_START, DEFAULT_AZIMUTH_START)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=360, step=1, unit_of_measurement="°",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_AZIMUTH_END, default=d(CONF_AZIMUTH_END, DEFAULT_AZIMUTH_END)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=360, step=1, unit_of_measurement="°",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_ELEVATION_MIN, default=d(CONF_ELEVATION_MIN, DEFAULT_ELEVATION_MIN)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=90, step=1, unit_of_measurement="°",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_ELEVATION_MAX, default=d(CONF_ELEVATION_MAX, DEFAULT_ELEVATION_MAX)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=90, step=1, unit_of_measurement="°",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_SHADE_POSITION, default=d(CONF_SHADE_POSITION, DEFAULT_SHADE_POSITION)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=100, step=1, unit_of_measurement="%",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            # --- Open / closed end positions ---
            vol.Required(
                CONF_OPEN_POSITION, default=d(CONF_OPEN_POSITION, DEFAULT_OPEN_POSITION)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=100, step=1, unit_of_measurement="%",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                CONF_CLOSED_POSITION,
                default=d(CONF_CLOSED_POSITION, DEFAULT_CLOSED_POSITION),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=100, step=1, unit_of_measurement="%",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            # --- Auto up (morning) ---
            vol.Required(
                CONF_AUTO_UP_ENABLED, default=d(CONF_AUTO_UP_ENABLED, True)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_UP_TRIGGER, default=d(CONF_UP_TRIGGER, DEFAULT_UP_TRIGGER)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=UP_TRIGGERS,
                    translation_key="trigger",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_UP_TIME, default=d(CONF_UP_TIME, DEFAULT_UP_TIME)
            ): selector.TimeSelector(),
            vol.Required(
                CONF_UP_TIME_WEEKEND,
                default=d(CONF_UP_TIME_WEEKEND, DEFAULT_UP_TIME_WEEKEND),
            ): selector.TimeSelector(),
            vol.Required(
                CONF_UP_OFFSET, default=d(CONF_UP_OFFSET, DEFAULT_UP_OFFSET)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-180, max=180, step=5, unit_of_measurement="min",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_UP_EARLIEST,
                description={"suggested_value": defaults.get(CONF_UP_EARLIEST)},
            ): selector.TimeSelector(),
            vol.Optional(
                CONF_UP_LATEST,
                description={"suggested_value": defaults.get(CONF_UP_LATEST)},
            ): selector.TimeSelector(),
            # --- Auto down (evening) ---
            vol.Required(
                CONF_AUTO_DOWN_ENABLED, default=d(CONF_AUTO_DOWN_ENABLED, True)
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_DOWN_TRIGGER, default=d(CONF_DOWN_TRIGGER, DEFAULT_DOWN_TRIGGER)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=DOWN_TRIGGERS,
                    translation_key="trigger",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_DOWN_TIME, default=d(CONF_DOWN_TIME, DEFAULT_DOWN_TIME)
            ): selector.TimeSelector(),
            vol.Required(
                CONF_DOWN_TIME_WEEKEND,
                default=d(CONF_DOWN_TIME_WEEKEND, DEFAULT_DOWN_TIME_WEEKEND),
            ): selector.TimeSelector(),
            vol.Required(
                CONF_DOWN_OFFSET, default=d(CONF_DOWN_OFFSET, DEFAULT_DOWN_OFFSET)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-180, max=180, step=5, unit_of_measurement="min",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_DOWN_EARLIEST,
                description={"suggested_value": defaults.get(CONF_DOWN_EARLIEST)},
            ): selector.TimeSelector(),
            vol.Optional(
                CONF_DOWN_LATEST,
                description={"suggested_value": defaults.get(CONF_DOWN_LATEST)},
            ): selector.TimeSelector(),
        }
    )


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
