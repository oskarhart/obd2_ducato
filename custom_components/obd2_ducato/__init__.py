"""OBD2 Ducato integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .bluetooth_manager import BluetoothManager
from .coordinator import OBD2Coordinator
from .const import (
    DOMAIN,
    CONF_MAC_ADDRESS,
    CONF_RFCOMM_PORT,
    CONF_RFCOMM_CHANNEL,
    DEFAULT_RFCOMM_PORT,
    DEFAULT_RFCOMM_CHANNEL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OBD2 Ducato from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    mac = entry.data[CONF_MAC_ADDRESS]
    rfcomm_port = entry.data.get(CONF_RFCOMM_PORT, DEFAULT_RFCOMM_PORT)
    rfcomm_channel = entry.data.get(CONF_RFCOMM_CHANNEL, DEFAULT_RFCOMM_CHANNEL)

    bt_manager = BluetoothManager(
        mac_address=mac,
        rfcomm_port=rfcomm_port,
        rfcomm_channel=rfcomm_channel,
    )

    # Set up Bluetooth
    bt_ok = await bt_manager.async_setup()
    if not bt_ok:
        _LOGGER.error(
            "Failed to set up Bluetooth for %s. "
            "Make sure the OBD2 adapter is plugged in and the vehicle is nearby.",
            mac,
        )
        # Don't fail entry setup entirely — coordinator will retry
    
    coordinator = OBD2Coordinator(
        hass=hass,
        bt_manager=bt_manager,
        name=f"OBD2 Ducato {mac}",
    )

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload OBD2 Ducato config entry."""
    coordinator: OBD2Coordinator = hass.data[DOMAIN].get(entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and coordinator:
        await coordinator.async_disconnect()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
