import pytest
import asyncio

from uav_sdk.core.sdk import UAVDriver
from uav_sdk.plugins.mavlink_plugin import MavlinkProtocolPlugin


class FakeHeartbeat:
    def __init__(self, base_mode=0x80, custom_mode=4):
        self.base_mode = base_mode
        self.custom_mode = custom_mode

    def get_type(self):
        return "HEARTBEAT"


@pytest.mark.asyncio
async def test_mavlink_protocol_plugin_event_state_integration():
    sdk = UAVDriver(log_level="CRITICAL")
    plugin = MavlinkProtocolPlugin(config={"use_pymavlink": False, "auto_connect": False}, runtime=sdk)

    assert await plugin.initialize()
    assert await plugin.start()

    messages = []

    def heartbeat_handler(event):
        messages.append(event)

    sdk.event_system.subscribe("mavlink.HEARTBEAT", heartbeat_handler)

    await plugin._on_mavlink_message(FakeHeartbeat(base_mode=0x80, custom_mode=3))

    await asyncio.sleep(0.01)

    assert len(messages) == 1
    assert sdk.state.get().armed is True
    assert sdk.state.get().mode == "3"

    assert await plugin.shutdown()
