"""The Shutter Control integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import ShutterControlManager

_LOGGER = logging.getLogger(__name__)

type ShutterControlConfigEntry = ConfigEntry[ShutterControlManager]

CARD_URL = "/shutter_control_frontend/shutter-control-card.js"
CARD_VERSION = "0.5.0"


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the Lovelace card and load it on the frontend (once)."""
    if hass.data.get(f"{DOMAIN}_card_registered"):
        return
    hass.data[f"{DOMAIN}_card_registered"] = True
    card_path = Path(__file__).parent / "www" / "shutter-control-card.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card_path), False)]
    )
    add_extra_js_url(hass, f"{CARD_URL}?v={CARD_VERSION}")


async def async_setup_entry(
    hass: HomeAssistant, entry: ShutterControlConfigEntry
) -> bool:
    """Set up Shutter Control from a config entry."""
    manager = ShutterControlManager(hass, entry)
    await manager.async_setup()
    entry.runtime_data = manager

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_register_card(hass)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ShutterControlConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and entry.runtime_data is not None:
        await entry.runtime_data.async_shutdown()
    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: ShutterControlConfigEntry
) -> None:
    """Reload the entry when options or subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)
