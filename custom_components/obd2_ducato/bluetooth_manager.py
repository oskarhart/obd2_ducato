"""Bluetooth manager for OBD2 Ducato - uses raw Python BT sockets, no rfcomm needed."""
from __future__ import annotations

import asyncio
import logging
import socket
import subprocess

_LOGGER = logging.getLogger(__name__)


class BluetoothManager:
    """Manages Bluetooth connection via raw Python socket (no rfcomm required)."""

    def __init__(self, mac_address: str, rfcomm_port: int = 0, rfcomm_channel: int = 1):
        self.mac_address = mac_address.upper()
        self.rfcomm_channel = rfcomm_channel
        self._socket: socket.socket | None = None

    @property
    def socket(self) -> socket.socket | None:
        """Return the raw BT socket."""
        return self._socket

    async def async_setup(self) -> bool:
        """Pair, trust, and open a Bluetooth socket. Returns True on success."""
        _LOGGER.debug("Setting up Bluetooth for %s", self.mac_address)

        if not await self._async_ensure_paired():
            return False

        return await self._async_connect_socket()

    async def async_ensure_connected(self) -> bool:
        """Ensure socket is open, reconnect if needed."""
        if self._socket is not None:
            try:
                # Send a zero-length check - will raise if socket is dead
                self._socket.getpeername()
                return True
            except Exception:
                _LOGGER.warning("BT socket lost, reconnecting...")
                self._close_socket()

        return await self._async_connect_socket()

    async def _async_connect_socket(self) -> bool:
        """Open a raw RFCOMM Bluetooth socket."""
        _LOGGER.info(
            "Opening BT socket to %s channel %d",
            self.mac_address, self.rfcomm_channel
        )
        try:
            sock = await self.hass_loop_connect()
            if sock:
                self._socket = sock
                _LOGGER.info("BT socket connected to %s", self.mac_address)
                return True
            return False
        except Exception as err:
            _LOGGER.error("BT socket connect error: %s", err)
            return False

    async def hass_loop_connect(self) -> socket.socket | None:
        """Connect BT socket in executor to avoid blocking event loop."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._blocking_connect)

    def _blocking_connect(self) -> socket.socket | None:
        """Blocking BT socket connect - runs in executor."""
        try:
            sock = socket.socket(
                socket.AF_BLUETOOTH,
                socket.SOCK_STREAM,
                socket.BTPROTO_RFCOMM
            )
            sock.settimeout(15)
            sock.connect((self.mac_address, self.rfcomm_channel))
            sock.settimeout(None)  # Back to blocking after connect
            return sock
        except OSError as err:
            _LOGGER.error(
                "Failed to connect BT socket to %s: %s", self.mac_address, err
            )
            return None

    def _close_socket(self):
        """Close the BT socket cleanly."""
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    async def _async_ensure_paired(self) -> bool:
        """Make sure the device is paired and trusted via bluetoothctl."""
        # Check if already paired
        if await self._async_is_paired():
            _LOGGER.debug("%s already paired", self.mac_address)
            await self._async_trust()
            return True

        _LOGGER.info("Pairing with %s...", self.mac_address)
        if not await self._async_pair():
            _LOGGER.error("Failed to pair with %s", self.mac_address)
            return False

        await self._async_trust()
        return True

    async def _async_bluetoothctl(self, *commands: str) -> tuple[int, str]:
        """Run bluetoothctl with a list of commands."""
        cmd_input = "\n".join(commands) + "\nexit\n"
        try:
            proc = await asyncio.create_subprocess_exec(
                "bluetoothctl",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(input=cmd_input.encode()), timeout=30
            )
            return proc.returncode or 0, stdout.decode()
        except asyncio.TimeoutError:
            _LOGGER.warning("bluetoothctl timed out")
            return -1, ""
        except FileNotFoundError:
            _LOGGER.error("bluetoothctl not found")
            return -1, ""
        except Exception as err:
            _LOGGER.error("bluetoothctl error: %s", err)
            return -1, ""

    async def _async_is_paired(self) -> bool:
        _, stdout = await self._async_bluetoothctl("paired-devices")
        return self.mac_address in stdout.upper()

    async def _async_pair(self) -> bool:
        """Power on and pair."""
        await self._async_bluetoothctl("power on")
        await asyncio.sleep(1)
        # Start scan briefly so device is discoverable
        await self._async_bluetoothctl("power on", "scan on")
        await asyncio.sleep(6)
        rc, stdout = await self._async_bluetoothctl(
            "power on",
            "agent NoInputNoOutput",
            "default-agent",
            f"pair {self.mac_address}",
        )
        await asyncio.sleep(1)
        return await self._async_is_paired()

    async def _async_trust(self):
        """Trust the device so it auto-connects."""
        await self._async_bluetoothctl(f"trust {self.mac_address}")
        _LOGGER.debug("Trusted %s", self.mac_address)

    async def async_teardown(self):
        """Close socket on unload."""
        self._close_socket()
        _LOGGER.debug("BT socket closed")
