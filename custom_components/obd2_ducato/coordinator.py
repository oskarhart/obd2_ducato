"""Data coordinator for OBD2 Ducato integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .bluetooth_manager import BluetoothManager
from .const import DOMAIN, SCAN_INTERVAL, SENSORS, DUCATO_CUSTOM_PIDS

_LOGGER = logging.getLogger(__name__)

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
        self._connection = None
        self._obd = None
        self._supported_sensors: set[str] = set()

    def _get_obd(self):
        """Lazy import obd module."""
        if self._obd is None:
            import obd  # noqa: PLC0415
            self._obd = obd
        return self._obd

    async def _async_connect(self) -> bool:
        """Connect to OBD2 adapter via BT socket."""
        try:
            obd = await self.hass.async_add_executor_job(self._get_obd)
        except Exception as err:
            _LOGGER.error("Failed to import obd library: %s", err)
            return False

        # Check existing connection
        if self._connection is not None:
            try:
                if self._connection.status() == obd.OBDStatus.CAR_CONNECTED:
                    return True
            except Exception:
                self._connection = None

        # Ensure BT socket is open
        if not await self.bt_manager.async_ensure_connected():
            _LOGGER.error("Could not open Bluetooth socket")
            return False

        sock = self.bt_manager.socket
        if sock is None:
            _LOGGER.error("BT socket is None after connect")
            return False

        try:
            _LOGGER.info("Connecting OBD2 via BT socket to %s", self.bt_manager.mac_address)
            # Pass the raw socket directly to python-obd
            self._connection = await self.hass.async_add_executor_job(
                lambda: obd.OBD(
                    portstr=None,
                    baudrate=None,
                    protocol=None,
                    fast=False,
                    timeout=10,
                    sock=sock,  # Pass raw socket
                )
            )

            if self._connection.status() == obd.OBDStatus.CAR_CONNECTED:
                _LOGGER.info("OBD2 connected successfully via BT socket")
                await self._async_probe_sensors()
                return True
            else:
                _LOGGER.warning("OBD2 status: %s", self._connection.status())
                return False

        except TypeError:
            # Some versions of python-obd don't support sock= parameter
            # Fall back to passing socket as a file-like object via port string workaround
            _LOGGER.warning("obd sock= not supported, trying serial_io workaround")
            return await self._async_connect_via_serial_io(obd, sock)

        except Exception as err:
            _LOGGER.error("OBD2 connection error: %s", err)
            self._connection = None
            return False

    async def _async_connect_via_serial_io(self, obd, sock) -> bool:
        """Fallback: wrap BT socket as a serial-like object for python-obd."""
        try:
            import io  # noqa: PLC0415

            class SocketSerial:
                """Wraps a BT socket to look like a serial port to python-obd."""
                def __init__(self, s):
                    self._sock = s
                    self.timeout = 10
                    self.baudrate = 38400
                    self.bytesize = 8
                    self.parity = 'N'
                    self.stopbits = 1
                    self.xonxoff = False
                    self.rtscts = False
                    self.dsrdtr = False
                    self.is_open = True

                def read(self, n):
                    return self._sock.recv(n)

                def write(self, data):
                    return self._sock.send(data)

                def flush(self):
                    pass

                def flushInput(self):
                    pass

                def flushOutput(self):
                    pass

                def close(self):
                    self._sock.close()

                def fileno(self):
                    return self._sock.fileno()

            serial_wrapper = SocketSerial(sock)

            self._connection = await self.hass.async_add_executor_job(
                lambda: obd.OBD(
                    portstr=None,
                    baudrate=None,
                    protocol=None,
                    fast=False,
                    timeout=10,
                    serial_io=serial_wrapper,
                )
            )

            if self._connection.status() == obd.OBDStatus.CAR_CONNECTED:
                _LOGGER.info("OBD2 connected via SocketSerial wrapper")
                await self._async_probe_sensors()
                return True

            _LOGGER.warning("OBD2 status via wrapper: %s", self._connection.status())
            return False

        except Exception as err:
            _LOGGER.error("SocketSerial fallback error: %s", err)
            self._connection = None
            return False

    async def _async_probe_sensors(self) -> None:
        """Probe which sensors the vehicle supports."""
        if not self._connection:
            return

        obd = self._obd
        _LOGGER.info("Probing supported OBD2 sensors...")
        self._supported_sensors = set()

        for sensor_id, sensor_def in SENSORS.items():
            if sensor_def["obd_command"] is None:
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
                    _LOGGER.debug("Supported: %s", sensor_id)
            except Exception as err:
                _LOGGER.debug("Error probing %s: %s", sensor_id, err)

        # Custom Ducato PIDs
        for sensor_id, sensor_def in DUCATO_CUSTOM_PIDS.items():
            result = await self._async_query_custom_pid(sensor_def["custom_pid"])
            if result is not None:
                self._supported_sensors.add(sensor_id)

        # Fuel consumption needs both MAF and speed
        if "maf" in self._supported_sensors and "speed" in self._supported_sensors:
            self._supported_sensors.add("fuel_consumption")

        _LOGGER.info(
            "Supported sensors: %s",
            ", ".join(self._supported_sensors) or "none",
        )

    def get_supported_sensors(self) -> dict:
        """Return supported sensor definitions."""
        result = {}
        for sensor_id in self._supported_sensors:
            if sensor_id in SENSORS:
                result[sensor_id] = SENSORS[sensor_id]
            elif sensor_id in DUCATO_CUSTOM_PIDS:
                result[sensor_id] = DUCATO_CUSTOM_PIDS[sensor_id]
        return result

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest data from OBD2."""
        if not await self._async_connect():
            raise UpdateFailed("Could not connect to OBD2 adapter")

        obd = self._obd
        data = {}

        for sensor_id in self._supported_sensors:
            if sensor_id not in SENSORS:
                continue
            sensor_def = SENSORS[sensor_id]
            if sensor_def["obd_command"] is None:
                continue
            try:
                cmd = getattr(obd.commands, sensor_def["obd_command"], None)
                if cmd is None:
                    continue
                response = await self.hass.async_add_executor_job(
                    self._connection.query, cmd
                )
                if not response.is_null():
                    val = response.value
                    if hasattr(val, "magnitude"):
                        val = round(float(val.magnitude), 2)
                    else:
                        val = round(float(val), 2)
                    data[sensor_id] = val
            except Exception as err:
                _LOGGER.debug("Error reading %s: %s", sensor_id, err)

        # Custom Ducato PIDs
        for sensor_id in self._supported_sensors:
            if sensor_id in DUCATO_CUSTOM_PIDS:
                sensor_def = DUCATO_CUSTOM_PIDS[sensor_id]
                result = await self._async_query_custom_pid(sensor_def["custom_pid"])
                if result is not None:
                    data[sensor_id] = result

        # Calculated fuel consumption
        if "fuel_consumption" in self._supported_sensors:
            maf = data.get("maf")
            speed = data.get("speed")
            if maf and speed and speed > 2:
                try:
                    fuel_rate = maf / DIESEL_AFR / DIESEL_DENSITY
                    data["fuel_consumption"] = round((fuel_rate * 3600 / speed) * 100, 1)
                except Exception:
                    pass

        return data

    async def _async_query_custom_pid(self, pid_def: dict | None) -> float | None:
        """Query a Fiat custom PID."""
        if not pid_def or not self._connection or not self._obd:
            return None
        try:
            obd = self._obd
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
                raw = response.messages[0].data[2:]
                return pid_def["formula"](raw)
        except Exception as err:
            _LOGGER.debug("Custom PID error: %s", err)
        return None

    async def async_disconnect(self) -> None:
        """Disconnect from OBD2 and release BT."""
        if self._connection:
            try:
                await self.hass.async_add_executor_job(self._connection.close)
            except Exception:
                pass
            self._connection = None
        await self.bt_manager.async_teardown()
