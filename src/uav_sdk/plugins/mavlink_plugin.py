from typing import Any, Dict

from uav_sdk.plugins.base import ProtocolPlugin, PluginInfo, PluginState
from uav_sdk.interfaces import MavlinkAdapter


class MavlinkProtocolPlugin(ProtocolPlugin):
    """Protocol plugin that bridges MAVLink to SDK events and state."""

    def __init__(self, config: Dict[str, Any], runtime):
        super().__init__(config, runtime)
        self.adapter = None

    def get_info(self):
        return PluginInfo(
            name="mavlink_protocol",
            version="0.1.0",
            author="SDK Team",
            description="MAVLink protocol plugin bridging SITL to SDK event/state",
            plugin_type="protocol",
            dependencies=[],
            features=["mavlink", "protocol"],
            config_schema={
                "connection": {"type": "string", "default": "tcp://127.0.0.1:5763"},
                "auto_connect": {"type": "boolean", "default": True},
            },
        )

    async def initialize(self) -> bool:
        self.adapter = MavlinkAdapter(
            config=self.config,
            on_message=self._on_mavlink_message,
        )

        self.runtime.set_protocol_adapter(self.adapter)

        if self.config.get("auto_connect", True):
            connected = await self.adapter.connect()
            if not connected:
                self.state = PluginState.ERROR
                return False

        self.state = PluginState.INITIALIZED
        return True

    async def start(self) -> bool:
        if self.adapter and self.adapter.is_connected():
            await self.runtime.event_system.publish("mavlink.plugin_started", status="connected")
        self.state = PluginState.STARTED
        return True

    async def _on_mavlink_message(self, msg):
        # Normalize and publish event
        msg_type = getattr(msg, "get_type", lambda: "unknown")()
        await self.runtime.event_system.publish(f"mavlink.{msg_type}", msg=msg)

        # Quick state mapping for common message types
        if msg_type == "HEARTBEAT":
            # Example: update armed status / mode from MAV mode flags
            base_mode = getattr(msg, "base_mode", None)
            mode = getattr(msg, "custom_mode", None)
            armed = bool(base_mode & 0x80) if base_mode is not None else False
            self.runtime.state.update(armed=armed, mode=str(mode))

    async def shutdown(self) -> bool:
        if self.adapter:
            await self.adapter.disconnect()
            await self.runtime.event_system.publish("mavlink.plugin_shutdown", status="disconnected")
        self.state = PluginState.STOPPED
        return True

    async def send_message(self, msg: Any) -> bool:
        if self.adapter:
            return await self.adapter.send(msg)
        return False

    async def receive_message(self, timeout: float = 0.1) -> Any:
        if self.adapter:
            return await self.adapter.receive(timeout=timeout)
        return None
