"""The Shutter Control integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import panel_custom
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import ShutterControlManager

_LOGGER = logging.getLogger(__name__)

type ShutterControlConfigEntry = ConfigEntry[ShutterControlManager]

FRONTEND_URL = "/shutter_control_frontend"
CARD_URL = f"{FRONTEND_URL}/shutter-control-card.js"
PANEL_URL = f"{FRONTEND_URL}/shutter-control-panel.js"
PANEL_PATH = "shutter-control"
FRONTEND_VERSION = "0.8.0"


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the card + panel, load the card and add the sidebar panel (once)."""
    if hass.data.get(f"{DOMAIN}_frontend_registered"):
        return
    hass.data[f"{DOMAIN}_frontend_registered"] = True

    www_dir = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_URL, str(www_dir), False)]
    )
    add_extra_js_url(hass, f"{CARD_URL}?v={FRONTEND_VERSION}")

    try:
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=PANEL_PATH,
            webcomponent_name="shutter-control-panel",
            module_url=f"{PANEL_URL}?v={FRONTEND_VERSION}",
            sidebar_title="Rollläden",
            sidebar_icon="mdi:window-shutter",
            require_admin=False,
            config={},
        )
    except ValueError:
        # Panel already registered (e.g. after a reload) - ignore.
        pass


async def async_setup_entry(
    hass: HomeAssistant, entry: ShutterControlConfigEntry
) -> bool:
    """Set up Shutter Control from a config entry."""
    manager = ShutterControlManager(hass, entry)
    await manager.async_setup()
    entry.runtime_data = manager

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_register_frontend(hass)
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
