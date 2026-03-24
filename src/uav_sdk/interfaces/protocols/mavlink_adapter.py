"""Simple MAVLink adapter implementation for Phase 2 groundwork."""

import asyncio
from typing import Any, Optional

try:
    from pymavlink import mavutil
except ImportError:
    mavutil = None

from .base import ProtocolCategory, ProtocolInterface


class MavlinkAdapter(ProtocolInterface):
    """A lightweight MAVLink protocol adapter stub."""

    def __init__(self, config: Optional[dict] = None, on_message=None):
        super().__init__(config)
        self.category = ProtocolCategory.MAVLINK
        self._receive_queue = asyncio.Queue()
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._incoming = asyncio.Queue()
        self._mavlink = None
        self._pymav_task = None
        self._on_message = on_message  # callback for received messages


    def _parse_connection(self):
        """Parse config connection string like tcp://host:port."""
        conn = self.config.get("connection", "tcp://127.0.0.1:5763")
        if isinstance(conn, str) and conn.startswith("tcp://"):
            _, addr = conn.split("tcp://", 1)
            host, port = addr.split(":")
            return host, int(port)
        raise ValueError(f"Unsupported connection value: {conn}")

    async def _background_reader(self):
        assert self._reader is not None
        while self._connected and not self._reader.at_eof():
            try:
                data = await asyncio.wait_for(self._reader.read(4096), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            if not data:
                break
            await self._incoming.put(data)

    async def _pymavlink_reader(self):
        assert self._mavlink is not None
        while self._connected:
            msg = self._mavlink.recv_match(blocking=True, timeout=1)
            if msg is not None:
                if self._on_message:
                    await self._on_message(msg)
                else:
                    await self._incoming.put(msg)
            await asyncio.sleep(0)

    async def connect(self) -> bool:
        conn_str = self.config.get("connection", "tcp://127.0.0.1:5763")

        if self.config.get("use_pymavlink", True) and mavutil is not None:
            try:
                if conn_str.startswith("tcp://"):
                    conn_str = conn_str.replace("tcp://", "tcp:")
                self._mavlink = mavutil.mavlink_connection(conn_str, autoreconnect=True)
                self._connected = True
                self.update_status("connected")
                self._pymav_task = asyncio.create_task(self._pymavlink_reader())
                return True
            except Exception as e:
                self.update_status(f"pymavlink-connect-error: {e}")
                # continue to socket fallback

        if self.config.get("connection"):
            try:
                host, port = self._parse_connection()
                self._reader, self._writer = await asyncio.open_connection(host, port)
                self._connected = True
                self.update_status("connected")
                self._reader_task = asyncio.create_task(self._background_reader())
                return True
            except Exception as e:
                self.update_status(f"connect-error: {e}")
                return False

        # Fallback local queue mode for early Phase 2 testing
        self._connected = True
        self.update_status("connected")
        return True

    async def disconnect(self) -> bool:
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None

        if self._mavlink:
            try:
                self._mavlink.close()
            except Exception:
                pass
            self._mavlink = None

        self._connected = False
        self.update_status("disconnected")

        if hasattr(self, "_reader_task") and not self._reader_task.done():
            self._reader_task.cancel()
            await asyncio.sleep(0)

        if hasattr(self, "_pymav_task") and self._pymav_task is not None and not self._pymav_task.done():
            self._pymav_task.cancel()
            await asyncio.sleep(0)

        return True

    async def send(self, data: Any) -> bool:
        if not self._connected:
            return False

        if self._mavlink is not None:
            try:
                if isinstance(data, bytes):
                    self._mavlink.write(data)
                elif hasattr(data, "pack"):
                    self._mavlink.mav.send(data)
                else:
                    self._mavlink.write(str(data).encode("utf-8"))
                self.update_status("sent")
                return True
            except Exception as e:
                self.update_status(f"pymavlink-send-error: {e}")
                return False

        if self._writer:
            if isinstance(data, bytes):
                msg_bytes = data
            else:
                msg_bytes = str(data).encode("utf-8")
            self._writer.write(msg_bytes)
            await self._writer.drain()
            self.update_status("sent")
            return True

        # Fallback queue behavior
        await self._receive_queue.put(data)
        self.update_status("sent")
        return True

    async def receive(self, timeout: float = 0.1) -> Optional[Any]:
        if not self._connected:
            return None

        data = None
        if self._reader:
            try:
                data = await asyncio.wait_for(self._incoming.get(), timeout)
            except asyncio.TimeoutError:
                return None
        else:
            try:
                data = await asyncio.wait_for(self._receive_queue.get(), timeout)
            except asyncio.TimeoutError:
                return None

        if isinstance(data, bytes):
            try:
                return data.decode("utf-8", errors="ignore")
            except Exception:
                return data

        return data

