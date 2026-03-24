"""Tests for protocol abstraction layer."""

import asyncio
import pytest

from uav_sdk.interfaces import ProtocolInterface, MavlinkAdapter
from uav_sdk.core.sdk import UAVDriver


class DummyProtocol(ProtocolInterface):
    async def connect(self) -> bool:
        self._connected = True
        return True

    async def disconnect(self) -> bool:
        self._connected = False
        return True

    async def send(self, data):
        if not self._connected:
            return False
        self.last = data
        return True

    async def receive(self, timeout: float = 0.1):
        if not self._connected:
            return None
        await asyncio.sleep(0)
        return getattr(self, "last", None)


def test_protocol_interface_contract():
    adapter = DummyProtocol()
    assert adapter.get_status() == "initialized"
    assert not adapter.is_connected()


@pytest.mark.asyncio
async def test_mavlink_adapter_flow():
    adapter = MavlinkAdapter(config={"use_pymavlink": False})
    assert await adapter.connect()
    assert adapter.is_connected()

    assert await adapter.send({'heartbeat': 1})
    received = await adapter.receive(timeout=0.5)
    assert received == {'heartbeat': 1}

    assert await adapter.disconnect()
    assert not adapter.is_connected()


@pytest.mark.asyncio
async def test_sdk_protocol_usage():
    sdk = UAVDriver(log_level="CRITICAL")
    adapter = DummyProtocol()
    sdk.set_protocol_adapter(adapter)

    assert await sdk.connect_protocol()
    assert await sdk.send_protocol_message("test")
    assert await sdk.receive_protocol_message() == "test"
    assert await sdk.disconnect_protocol()


@pytest.mark.asyncio
async def test_mavlink_adapter_tcp_connection():
    async def echo_server(reader, writer):
        data = await reader.readline()
        writer.write(data)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(echo_server, '127.0.0.1', 0)
    host, port = server.sockets[0].getsockname()[:2]

    try:
        adapter = MavlinkAdapter(config={"connection": f"tcp://{host}:{port}", "use_pymavlink": False})
        assert await adapter.connect()

        assert await adapter.send("vehicle-connect\n")
        response = await adapter.receive(timeout=1.0)
        assert response.strip() == "vehicle-connect"

        assert await adapter.disconnect()
    finally:
        server.close()
        await server.wait_closed()
