"""Bluetooth manager for OBD2 Ducato integration."""
from __future__ import annotations

import asyncio
import logging
import subprocess
import os
import re

_LOGGER = logging.getLogger(__name__)

RFCOMM_DEVICE_TEMPLATE = "/dev/rfcomm{}"


class BluetoothManager:
    """Manages Bluetooth pairing and rfcomm serial binding."""

    def __init__(self, mac_address: str, rfcomm_port: int = 0, rfcomm_channel: int = 1):
        self.mac_address = mac_address.upper()
        self.rfcomm_port = rfcomm_port
        self.rfcomm_channel = rfcomm_channel
        self.device_path = RFCOMM_DEVICE_TEMPLATE.format(rfcomm_port)

    async def async_setup(self) -> bool:
        """Pair, trust, and bind the BT device. Returns True on success."""
        _LOGGER.debug("Setting up Bluetooth for %s", self.mac_address)

        if not await self._async_is_paired():
            _LOGGER.info("Device not paired, attempting to pair %s", self.mac_address)
            if not await self._async_pair():
                _LOGGER.error("Failed to pair with %s", self.mac_address)
                return False

        if not await self._async_is_trusted():
            await self._async_trust()

        if not await self._async_bind_rfcomm():
            return False

        _LOGGER.info("Bluetooth setup complete, device at %s", self.device_path)
        return True

    async def async_teardown(self):
        """Release rfcomm binding."""
        try:
            await asyncio.create_subprocess_exec(
                "rfcomm", "release", str(self.rfcomm_port),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            _LOGGER.debug("Released rfcomm%d", self.rfcomm_port)
        except Exception as err:
            _LOGGER.warning("Error releasing rfcomm: %s", err)

    async def _async_run(self, *args) -> tuple[int, str, str]:
        """Run a subprocess and return (returncode, stdout, stderr)."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
            return proc.returncode, stdout.decode().strip(), stderr.decode().strip()
        except asyncio.TimeoutError:
            _LOGGER.warning("Subprocess timed out: %s", args)
            return -1, "", "timeout"
        except Exception as err:
            _LOGGER.error("Subprocess error %s: %s", args, err)
            return -1, "", str(err)

    async def _async_bluetoothctl(self, *commands) -> tuple[int, str, str]:
        """Run bluetoothctl with a sequence of commands."""
        cmd_str = "\n".join(commands) + "\nexit\n"
        try:
            proc = await asyncio.create_subprocess_exec(
                "bluetoothctl",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=cmd_str.encode()), timeout=30
            )
            return proc.returncode, stdout.decode().strip(), stderr.decode().strip()
        except asyncio.TimeoutError:
            _LOGGER.warning("bluetoothctl timed out")
            return -1, "", "timeout"
        except Exception as err:
            _LOGGER.error("bluetoothctl error: %s", err)
            return -1, "", str(err)

    async def _async_is_paired(self) -> bool:
        """Check if device is already paired."""
        rc, stdout, _ = await self._async_bluetoothctl("paired-devices")
        return self.mac_address in stdout.upper()

    async def _async_is_trusted(self) -> bool:
        """Check if device is trusted."""
        rc, stdout, _ = await self._async_bluetoothctl(f"info {self.mac_address}")
        return "Trusted: yes" in stdout

    async def _async_pair(self) -> bool:
        """Scan and pair with the device."""
        _LOGGER.info("Starting BT scan to find %s", self.mac_address)

        # Power on adapter
        await self._async_bluetoothctl("power on")
        await asyncio.sleep(1)

        # Start scan, wait for device, then pair
        rc, stdout, _ = await self._async_bluetoothctl(
            "power on",
            "agent NoInputNoOutput",
            "default-agent",
            "scan on",
        )
        await asyncio.sleep(8)  # Give time for scan to find device

        rc, stdout, stderr = await self._async_bluetoothctl(
            "power on",
            "agent NoInputNoOutput",
            "default-agent",
            f"pair {self.mac_address}",
        )
        await asyncio.sleep(2)

        return await self._async_is_paired()

    async def _async_trust(self) -> bool:
        """Trust the device."""
        rc, stdout, _ = await self._async_bluetoothctl(
            f"trust {self.mac_address}"
        )
        _LOGGER.debug("Trust result for %s: %s", self.mac_address, stdout)
        return rc == 0

    async def _async_bind_rfcomm(self) -> bool:
        """Bind device to rfcomm serial port."""
        # Check if already bound
        if os.path.exists(self.device_path):
            _LOGGER.debug("%s already exists", self.device_path)
            return True

        _LOGGER.info(
            "Binding %s to %s (channel %d)",
            self.mac_address, self.device_path, self.rfcomm_channel
        )

        rc, stdout, stderr = await self._async_run(
            "rfcomm", "bind",
            str(self.rfcomm_port),
            self.mac_address,
            str(self.rfcomm_channel),
        )

        if rc != 0:
            _LOGGER.error(
                "rfcomm bind failed (rc=%d): %s", rc, stderr
            )
            return False

        # Short wait for device to appear
        for _ in range(5):
            if os.path.exists(self.device_path):
                return True
            await asyncio.sleep(0.5)

        _LOGGER.error("%s did not appear after rfcomm bind", self.device_path)
        return False

    async def async_ensure_connected(self) -> bool:
        """Ensure rfcomm device exists, re-bind if needed."""
        if os.path.exists(self.device_path):
            return True
        _LOGGER.warning("%s missing, attempting re-bind", self.device_path)
        return await self._async_bind_rfcomm()
