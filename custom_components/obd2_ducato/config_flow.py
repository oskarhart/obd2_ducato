"""Config flow for OBD2 Ducato integration."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_MAC_ADDRESS,
    CONF_RFCOMM_PORT,
    CONF_RFCOMM_CHANNEL,
    DEFAULT_RFCOMM_PORT,
    DEFAULT_RFCOMM_CHANNEL,
)
from .bluetooth_manager import BluetoothManager

_LOGGER = logging.getLogger(__name__)

MAC_REGEX = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def _validate_mac(mac: str) -> str:
    mac = mac.strip().upper()
    if not MAC_REGEX.match(mac):
        raise vol.Invalid("Invalid MAC address format. Use XX:XX:XX:XX:XX:XX")
    return mac


STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC_ADDRESS): str,
        vol.Optional(CONF_RFCOMM_PORT, default=DEFAULT_RFCOMM_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=9)
        ),
        vol.Optional(CONF_RFCOMM_CHANNEL, default=DEFAULT_RFCOMM_CHANNEL): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=30)
        ),
    }
)


async def _async_scan_bluetooth(hass: HomeAssistant) -> list[str]:
    """Scan for nearby Bluetooth devices and return MAC addresses."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "bluetoothctl", "scan", "on",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.sleep(8)
        proc.terminate()

        devices_proc = await asyncio.create_subprocess_exec(
            "bluetoothctl", "devices",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await devices_proc.communicate()
        lines = stdout.decode().strip().splitlines()
        macs = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                mac = parts[1]
                if MAC_REGEX.match(mac):
                    name = " ".join(parts[2:]) if len(parts) > 2 else mac
                    macs.append(f"{mac} ({name})")
        return macs
    except Exception as err:
        _LOGGER.warning("BT scan error: %s", err)
        return []


class OBD2DucatoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for OBD2 Ducato."""

    VERSION = 1

    def __init__(self):
        self._discovered_devices: list[str] = []
        self._scan_done = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                mac = _validate_mac(user_input[CONF_MAC_ADDRESS])
            except vol.Invalid:
                errors[CONF_MAC_ADDRESS] = "invalid_mac"
            else:
                # Check for duplicate
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()

                # Try to set up BT connection
                bt_manager = BluetoothManager(
                    mac_address=mac,
                    rfcomm_port=user_input.get(CONF_RFCOMM_PORT, DEFAULT_RFCOMM_PORT),
                    rfcomm_channel=user_input.get(CONF_RFCOMM_CHANNEL, DEFAULT_RFCOMM_CHANNEL),
                )

                success = await bt_manager.async_setup()
                if not success:
                    errors["base"] = "bt_connect_failed"
                else:
                    return self.async_create_entry(
                        title=f"OBD2 Ducato ({mac})",
                        data={
                            CONF_MAC_ADDRESS: mac,
                            CONF_RFCOMM_PORT: user_input.get(CONF_RFCOMM_PORT, DEFAULT_RFCOMM_PORT),
                            CONF_RFCOMM_CHANNEL: user_input.get(CONF_RFCOMM_CHANNEL, DEFAULT_RFCOMM_CHANNEL),
                        },
                    )

        # Scan for BT devices to help user
        if not self._scan_done:
            self._discovered_devices = await _async_scan_bluetooth(self.hass)
            self._scan_done = True

        description_placeholders = {}
        if self._discovered_devices:
            description_placeholders["devices"] = "\n".join(self._discovered_devices)
        else:
            description_placeholders["devices"] = "No devices found nearby"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OBD2DucatoOptionsFlow(config_entry)


class OBD2DucatoOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_RFCOMM_PORT,
                    default=self.config_entry.data.get(CONF_RFCOMM_PORT, DEFAULT_RFCOMM_PORT),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=9)),
                vol.Optional(
                    CONF_RFCOMM_CHANNEL,
                    default=self.config_entry.data.get(CONF_RFCOMM_CHANNEL, DEFAULT_RFCOMM_CHANNEL),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)
