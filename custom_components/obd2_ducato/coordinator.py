"""Data coordinator for OBD2 Ducato integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import obd
from obd import OBDStatus

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .bluetooth_manager import BluetoothManager
from .const import DOMAIN, SCAN_INTERVAL, SENSORS, DUCATO_CUSTOM_PIDS

_LOGGER = logging.getLogger(__name__)

# Diesel fuel consumption calculation constant
# Based on: L/100km = (MAF g/s * 3600) / (fuel_density * 10 * speed)
# Diesel density ~832 g/L, stoich AFR ~14.5 for diesel
DIESEL_DENSITY = 832  # g/L
DIESEL_AFR = 14.5


class OBD2Coordinator(DataUpdateCoordinator):
    """Coordinator to poll OBD2 data from the vehicle."""

    def __init__(
        self,
        hass: HomeAssistant,
        bt_manager: BluetoothManager,
        name: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.bt_manager = bt_manager
        self.device_name = name
        self._connection: obd.OBD | None = None
        self._supported_sensors: set[str] = set()
        self._available_sensors: dict[str, Any] = {}

    async def _async_connect(self) -> bool:
        """Connect to OBD2 adapter."""
        if self._connection and self._connection.status() == OBDStatus.CAR_CONNECTED:
            return True

        # Ensure BT rfcomm device is available
        if not await self.bt_manager.async_ensure_connected():
            return False

        try:
            _LOGGER.info("Connecting to OBD2 on %s", self.bt_manager.device_path)
            self._connection = await self.hass.async_add_executor_job(
                lambda: obd.OBD(
                    portstr=self.bt_manager.device_path,
                    baudrate=38400,
                    protocol=None,  # Auto-detect
                    fast=False,
                    timeout=10,
                )
            )

            if self._connection.status() == OBDStatus.CAR_CONNECTED:
                _LOGGER.info("OBD2 connected successfully")
                await self._async_probe_sensors()
                return True
            else:
                _LOGGER.warning(
                    "OBD2 connection status: %s", self._connection.status()
                )
                return False

        except Exception as err:
            _LOGGER.error("OBD2 connection error: %s", err)
            self._connection = None
            return False

    async def _async_probe_sensors(self) -> None:
        """Probe which sensors are supported by this vehicle."""
        if not self._connection:
            return

        _LOGGER.info("Probing supported OBD2 sensors...")
        self._supported_sensors = set()

        for sensor_id, sensor_def in SENSORS.items():
            if sensor_def["obd_command"] is None:
                # Calculated sensors - check dependencies
                if sensor_id == "fuel_consumption":
                    if "maf" in self._supported_sensors and "speed" in self._supported_sensors:
                        self._supported_sensors.add(sensor_id)
                continue

            try:
                cmd = getattr(obd.commands, sensor_def["obd_command"], None)
                if cmd is None:
                    continue

                supported = await self.hass.async_add_executor_job(
                    self._connection.supports, cmd
                )
                if supported:
                    self._supported_sensors.add(sensor_id)
                    _LOGGER.debug("Sensor supported: %s", sensor_id)
                else:
                    _LOGGER.debug("Sensor not supported: %s", sensor_id)

            except Exception as err:
                _LOGGER.debug("Error probing %s: %s", sensor_id, err)

        # Probe custom Ducato PIDs
        for sensor_id, sensor_def in DUCATO_CUSTOM_PIDS.items():
            result = await self._async_query_custom_pid(sensor_def["custom_pid"])
            if result is not None:
                self._supported_sensors.add(sensor_id)
                _LOGGER.debug("Custom PID supported: %s", sensor_id)

        # Now check fuel_consumption dependencies
        if "maf" in self._supported_sensors and "speed" in self._supported_sensors:
            self._supported_sensors.add("fuel_consumption")

        _LOGGER.info(
            "Supported sensors: %s",
            ", ".join(self._supported_sensors) or "none"
        )

    def get_supported_sensors(self) -> dict:
        """Return dict of all supported sensors with their definitions."""
        result = {}
        for sensor_id in self._supported_sensors:
            if sensor_id in SENSORS:
                result[sensor_id] = SENSORS[sensor_id]
            elif sensor_id in DUCATO_CUSTOM_PIDS:
                result[sensor_id] = DUCATO_CUSTOM_PIDS[sensor_id]
        return result

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from OBD2 adapter."""
        if not await self._async_connect():
            raise UpdateFailed("Could not connect to OBD2 adapter")

        data = {}

        # Poll standard OBD2 sensors
        for sensor_id in self._supported_sensors:
            if sensor_id in SENSORS:
                sensor_def = SENSORS[sensor_id]

                if sensor_def["obd_command"] is None:
                    continue  # Calculated later

                try:
                    cmd = getattr(obd.commands, sensor_def["obd_command"], None)
                    if cmd is None:
                        continue

                    response = await self.hass.async_add_executor_job(
                        self._connection.query, cmd
                    )

                    if not response.is_null():
                        val = response.value
                        # Extract magnitude if pint quantity
                        if hasattr(val, "magnitude"):
                            val = round(float(val.magnitude), 2)
                        else:
                            val = round(float(val), 2)
                        data[sensor_id] = val

                except Exception as err:
                    _LOGGER.debug("Error reading %s: %s", sensor_id, err)

        # Poll custom Ducato PIDs
        for sensor_id in self._supported_sensors:
            if sensor_id in DUCATO_CUSTOM_PIDS:
                sensor_def = DUCATO_CUSTOM_PIDS[sensor_id]
                result = await self._async_query_custom_pid(sensor_def["custom_pid"])
                if result is not None:
                    data[sensor_id] = result

        # Calculate fuel consumption from MAF and speed
        if "fuel_consumption" in self._supported_sensors:
            maf = data.get("maf")
            speed = data.get("speed")
            if maf and speed and speed > 2:
                try:
                    # L/100km = (MAF / AFR / density) * 3600 / speed * 100
                    fuel_rate_l_per_s = maf / DIESEL_AFR / DIESEL_DENSITY
                    fuel_per_100km = (fuel_rate_l_per_s * 3600 / speed) * 100
                    data["fuel_consumption"] = round(fuel_per_100km, 1)
                except Exception:
                    pass

        return data

    async def _async_query_custom_pid(self, pid_def: dict | None) -> float | None:
        """Query a custom/manufacturer PID."""
        if not pid_def or not self._connection:
            return None

        try:
            cmd_str = f"{pid_def['mode']} {pid_def['pid']}"

            response = await self.hass.async_add_executor_job(
                lambda: self._connection.query(
                    obd.OBDCommand(
                        pid_def["pid"],
                        "Custom",
                        bytes.fromhex(pid_def["mode"] + pid_def["pid"]),
                        pid_def["bytes"],
                        lambda messages: messages,
                    )
                )
            )

            if response and not response.is_null() and response.messages:
                raw = response.messages[0].data[2:]  # Strip header bytes
                return pid_def["formula"](raw)

        except Exception as err:
            _LOGGER.debug("Custom PID query error: %s", err)

        return None

    async def async_disconnect(self) -> None:
        """Disconnect OBD2 and BT."""
        if self._connection:
            try:
                await self.hass.async_add_executor_job(self._connection.close)
            except Exception:
                pass
            self._connection = None

        await self.bt_manager.async_teardown()
