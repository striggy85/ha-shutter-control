"""Per-cover automation enable/disable switch."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import ShutterControlConfigEntry
from .const import DOMAIN, SIGNAL_UPDATE
from .coordinator import CoverState, ShutterControlManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ShutterControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    manager = entry.runtime_data
    for subentry_id, cover in manager.covers.items():
        async_add_entities(
            [ShutterAutomaticSwitch(entry, manager, cover)],
            config_subentry_id=subentry_id,
        )


class ShutterAutomaticSwitch(SwitchEntity, RestoreEntity):
    """Switch that enables/disables automation for one cover."""

    _attr_has_entity_name = True
    _attr_name = "Automatic"
    _attr_icon = "mdi:window-shutter-auto"

    def __init__(
        self,
        entry: ShutterControlConfigEntry,
        manager: ShutterControlManager,
        cover: CoverState,
    ) -> None:
        self._entry = entry
        self._manager = manager
        self._subentry_id = cover.subentry_id
        self._attr_unique_id = f"{entry.entry_id}_{cover.subentry_id}_automatic"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, cover.subentry_id)},
            "name": cover.name,
            "manufacturer": "Shutter Control",
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None:
            self._manager.set_automatic(
                self._subentry_id, last.state == "on"
            )
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
    def is_on(self) -> bool:
        cover = self._manager.covers.get(self._subentry_id)
        return bool(cover and cover.automatic_enabled)

    async def async_turn_on(self, **kwargs) -> None:
        self._manager.set_automatic(self._subentry_id, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._manager.set_automatic(self._subentry_id, False)
        self.async_write_ha_state()
