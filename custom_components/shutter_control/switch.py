"""Per-group switches: automation on/off + the two door-contact behaviours."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import ShutterControlConfigEntry
from .const import CONF_DOOR_SENSOR, DOMAIN, SIGNAL_UPDATE
from .coordinator import CoverState, ShutterControlManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ShutterControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    manager = entry.runtime_data
    for subentry_id, cover in manager.covers.items():
        entities: list[SwitchEntity] = [
            ShutterToggle(
                entry,
                manager,
                cover,
                key="automatic",
                role="automatic",
                icon="mdi:window-shutter-auto",
                getter=lambda c: c.automatic_enabled,
                setter=manager.set_automatic,
            )
        ]
        # Door switches only make sense when a contact is configured.
        if cover.config.get(CONF_DOOR_SENSOR):
            entities.append(
                ShutterToggle(
                    entry,
                    manager,
                    cover,
                    key="door_action",
                    role="door_action",
                    icon="mdi:door-open",
                    getter=lambda c: c.door_action_enabled,
                    setter=manager.set_door_action,
                )
            )
            entities.append(
                ShutterToggle(
                    entry,
                    manager,
                    cover,
                    key="door_restore",
                    role="door_restore",
                    icon="mdi:arrow-down-bold-box-outline",
                    getter=lambda c: c.door_restore_enabled,
                    setter=manager.set_door_restore,
                )
            )
        async_add_entities(entities, config_subentry_id=subentry_id)


class ShutterToggle(SwitchEntity, RestoreEntity):
    """A persisted on/off toggle backed by a flag on the cover state."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ShutterControlConfigEntry,
        manager: ShutterControlManager,
        cover: CoverState,
        *,
        key: str,
        role: str,
        icon: str,
        getter: Callable[[CoverState], bool],
        setter: Callable[[str, bool], None],
    ) -> None:
        self._entry = entry
        self._manager = manager
        self._subentry_id = cover.subentry_id
        self._role = role
        self._getter = getter
        self._setter = setter
        self._attr_icon = icon
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{cover.subentry_id}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, cover.subentry_id)},
            "name": cover.name,
            "manufacturer": "Shutter Control",
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None:
            self._setter(self._subentry_id, last.state == "on")
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
        return bool(cover and self._getter(cover))

    @property
    def extra_state_attributes(self) -> dict:
        # Lets the dashboard card find each switch by its role.
        return {"sc_role": self._role}

    async def async_turn_on(self, **kwargs) -> None:
        self._setter(self._subentry_id, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._setter(self._subentry_id, False)
        self.async_write_ha_state()
