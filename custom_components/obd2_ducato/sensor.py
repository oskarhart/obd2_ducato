"""Sensor platform for OBD2 Ducato integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_MAC_ADDRESS
from .coordinator import OBD2Coordinator

_LOGGER = logging.getLogger(__name__)

STATE_CLASS_MAP = {
    "measurement": SensorStateClass.MEASUREMENT,
    "total_increasing": SensorStateClass.TOTAL_INCREASING,
    "total": SensorStateClass.TOTAL,
}

DEVICE_CLASS_MAP = {
    "temperature": SensorDeviceClass.TEMPERATURE,
    "voltage": SensorDeviceClass.VOLTAGE,
    "speed": SensorDeviceClass.SPEED,
    "duration": SensorDeviceClass.DURATION,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OBD2 sensors from config entry."""
    coordinator: OBD2Coordinator = hass.data[DOMAIN][entry.entry_id]

    # Wait for first data fetch so we know which sensors are supported
    await coordinator.async_config_entry_first_refresh()

    supported = coordinator.get_supported_sensors()
    mac = entry.data[CONF_MAC_ADDRESS]

    entities = [
        OBD2SensorEntity(coordinator, sensor_id, sensor_def, mac, entry.entry_id)
        for sensor_id, sensor_def in supported.items()
    ]

    if entities:
        _LOGGER.info("Adding %d OBD2 sensor entities", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.warning(
            "No supported OBD2 sensors found. "
            "Check that the engine is running and the adapter is connected."
        )


class OBD2SensorEntity(CoordinatorEntity, SensorEntity):
    """Representation of an OBD2 sensor."""

    def __init__(
        self,
        coordinator: OBD2Coordinator,
        sensor_id: str,
        sensor_def: dict,
        mac: str,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._sensor_id = sensor_id
        self._sensor_def = sensor_def
        self._mac = mac
        self._entry_id = entry_id

        self._attr_unique_id = f"{entry_id}_{sensor_id}"
        self._attr_name = sensor_def["name"]
        self._attr_icon = sensor_def.get("icon")
        self._attr_native_unit_of_measurement = sensor_def.get("unit")

        dc = sensor_def.get("device_class")
        self._attr_device_class = DEVICE_CLASS_MAP.get(dc) if dc else None

        sc = sensor_def.get("state_class")
        self._attr_state_class = STATE_CLASS_MAP.get(sc) if sc else None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=f"OBD2 Ducato ({self._mac})",
            manufacturer="Fiat",
            model="Ducato 2.3 JTD",
            sw_version="OBD2",
        )

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._sensor_id)

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self._sensor_id in self.coordinator.data
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "sensor_id": self._sensor_id,
            "mac_address": self._mac,
        }
