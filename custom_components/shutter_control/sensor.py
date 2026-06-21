"""Per-cover status sensor (idle / open / closed / shading / manual / disabled)."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ShutterControlConfigEntry
from .const import (
    DOMAIN,
    MODE_CLOSED,
    MODE_DISABLED,
    MODE_IDLE,
    MODE_MANUAL,
    MODE_OPEN,
    MODE_SHADING,
    SIGNAL_UPDATE,
)
from .coordinator import CoverState, ShutterControlManager

MODES = [
    MODE_IDLE,
    MODE_OPEN,
    MODE_CLOSED,
    MODE_SHADING,
    MODE_MANUAL,
    MODE_DISABLED,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ShutterControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    manager = entry.runtime_data
    for subentry_id, cover in manager.covers.items():
        async_add_entities(
            [ShutterStatusSensor(entry, manager, cover)],
            config_subentry_id=subentry_id,
        )


class ShutterStatusSensor(SensorEntity):
    """Reports the current automation mode of a cover."""

    _attr_has_entity_name = True
    _attr_name = "Status"
    _attr_icon = "mdi:window-shutter"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = MODES

    def __init__(
        self,
        entry: ShutterControlConfigEntry,
        manager: ShutterControlManager,
        cover: CoverState,
    ) -> None:
        self._entry = entry
        self._manager = manager
        self._subentry_id = cover.subentry_id
        self._attr_unique_id = f"{entry.entry_id}_{cover.subentry_id}_status"
        self._attr_translation_key = "status"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, cover.subentry_id)},
            "name": cover.name,
            "manufacturer": "Shutter Control",
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE.format(entry_id=self._entry.entry_id),
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> str | None:
        cover = self._manager.covers.get(self._subentry_id)
        return cover.mode if cover else None

    @property
    def extra_state_attributes(self) -> dict:
        cover = self._manager.covers.get(self._subentry_id)
        if cover is None:
            return {}
        return {
            "manual_override": cover.manual_override,
            "shading_active": cover.shading_active,
            "automatic_enabled": cover.automatic_enabled,
            "last_commanded_position": cover.last_commanded,
            "controlled_entity": cover.entity_id,
        }
