"""Config flow for OBD2 Ducato integration."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    DOMAIN,
    CONF_MAC_ADDRESS,
    CONF_RFCOMM_PORT,
    CONF_RFCOMM_CHANNEL,
    DEFAULT_RFCOMM_PORT,
    DEFAULT_RFCOMM_CHANNEL,
)

_LOGGER = logging.getLogger(__name__)

MAC_REGEX = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def _validate_mac(mac: str) -> str:
    mac = mac.strip().upper()
    if not MAC_REGEX.match(mac):
        raise vol.Invalid("Invalid MAC address format. Use XX:XX:XX:XX:XX:XX")
    return mac


STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC_ADDRESS): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Optional(CONF_RFCOMM_PORT, default=DEFAULT_RFCOMM_PORT): NumberSelector(
            NumberSelectorConfig(min=0, max=9, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_RFCOMM_CHANNEL, default=DEFAULT_RFCOMM_CHANNEL): NumberSelector(
            NumberSelectorConfig(min=1, max=30, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)


class OBD2DucatoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for OBD2 Ducato."""

    VERSION = 1

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
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"OBD2 Ducato ({mac})",
                    data={
                        CONF_MAC_ADDRESS: mac,
                        CONF_RFCOMM_PORT: user_input.get(
                            CONF_RFCOMM_PORT, DEFAULT_RFCOMM_PORT
                        ),
                        CONF_RFCOMM_CHANNEL: user_input.get(
                            CONF_RFCOMM_CHANNEL, DEFAULT_RFCOMM_CHANNEL
                        ),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "OBD2DucatoOptionsFlow":
        """Return the options flow."""
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
                    default=self.config_entry.data.get(
                        CONF_RFCOMM_PORT, DEFAULT_RFCOMM_PORT
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(min=0, max=9, step=1, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(
                    CONF_RFCOMM_CHANNEL,
                    default=self.config_entry.data.get(
                        CONF_RFCOMM_CHANNEL, DEFAULT_RFCOMM_CHANNEL
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(min=1, max=30, step=1, mode=NumberSelectorMode.BOX)
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)
