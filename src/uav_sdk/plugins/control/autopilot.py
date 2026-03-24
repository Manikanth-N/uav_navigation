"""
Autopilot control plugin for UAV navigation.

Handles vehicle control commands like arm, takeoff, land, and navigation.
"""

from typing import Any, Dict, Optional
import asyncio
import logging

from uav_sdk.plugins.base import ComputePlugin, PluginInfo, PluginState

logger = logging.getLogger(__name__)


class AutopilotPlugin(ComputePlugin):
    """Autopilot control plugin for vehicle commands."""

    def __init__(self, config: Dict[str, Any], runtime):
        super().__init__(config, runtime)
        self._mission_callback = None
        self._heartbeat_callback = None

    def get_info(self):
        return PluginInfo(
            name="autopilot",
            version="0.1.0",
            author="SDK Team",
            description="Vehicle autopilot control and command execution",
            plugin_type="control",
            dependencies=["mavlink_protocol", "mission_planner"],
            features=["arming", "takeoff", "landing", "navigation"],
            config_schema={
                "takeoff_altitude": {"type": "number", "default": 10.0},
                "cruise_speed": {"type": "number", "default": 5.0},
                "auto_arm": {"type": "boolean", "default": False},
            },
        )

    async def initialize(self) -> bool:
        # Subscribe to mission events
        self._mission_callback = self._on_mission_event
        self.subscribe("mission.*", self._mission_callback)

        # Subscribe to heartbeat for mode monitoring
        self._heartbeat_callback = self._on_heartbeat
        self.subscribe("mavlink.HEARTBEAT", self._heartbeat_callback)

        self.state = PluginState.INITIALIZED
        logger.info("Autopilot initialized")
        return True

    async def start(self) -> bool:
        # Auto-arm if configured
        if self.config.get("auto_arm", False):
            await asyncio.sleep(1.0)  # Wait for system to stabilize
            await self._arm_vehicle()

        self.state = PluginState.STARTED
        logger.info("Autopilot started")
        return True

    async def shutdown(self) -> bool:
        # Disarm on shutdown
        await self._disarm_vehicle()
        self.state = PluginState.STOPPED
        logger.info("Autopilot shutdown")
        return True

    async def process(self, input_data: Any) -> Any:
        """Process control commands."""
        if isinstance(input_data, dict):
            command = input_data.get("command")
            if command == "arm":
                return await self._arm_vehicle()
            elif command == "disarm":
                return await self._disarm_vehicle()
            elif command == "takeoff":
                altitude = input_data.get("altitude", self.config.get("takeoff_altitude", 10.0))
                return await self._takeoff(altitude)
            elif command == "land":
                return await self._land()
            elif command == "goto":
                return await self._goto_location(
                    input_data["lat"], input_data["lon"], input_data["alt"]
                )
            elif command == "set_mode":
                return await self._set_mode(input_data["mode"])
            elif command == "get_status":
                return self._get_status()

        return {"error": "Unknown command"}

    async def _arm_vehicle(self) -> Dict:
        """Arm the vehicle."""
        try:
            # Send MAVLink ARM command
            arm_msg = {
                "type": "COMMAND_LONG",
                "param1": 1,  # ARM
                "param2": 0,
                "param3": 0,
                "param4": 0,
                "param5": 0,
                "param6": 0,
                "param7": 0,
                "command": 400,  # MAV_CMD_COMPONENT_ARM_DISARM
                "target_system": 1,
                "target_component": 1,
            }

            success = await self.runtime.protocol_adapter.send(arm_msg)
            if success:
                logger.info("Vehicle arm command sent")
                await self.runtime.event_system.publish("autopilot.armed")
                return {"status": "success", "message": "Arm command sent"}
            else:
                return {"status": "error", "message": "Failed to send arm command"}

        except Exception as e:
            logger.error(f"Arm command failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _disarm_vehicle(self) -> Dict:
        """Disarm the vehicle."""
        try:
            disarm_msg = {
                "type": "COMMAND_LONG",
                "param1": 0,  # DISARM
                "param2": 0,
                "param3": 0,
                "param4": 0,
                "param5": 0,
                "param6": 0,
                "param7": 0,
                "command": 400,  # MAV_CMD_COMPONENT_ARM_DISARM
                "target_system": 1,
                "target_component": 1,
            }

            success = await self.runtime.protocol_adapter.send(disarm_msg)
            if success:
                logger.info("Vehicle disarm command sent")
                await self.runtime.event_system.publish("autopilot.disarmed")
                return {"status": "success", "message": "Disarm command sent"}
            else:
                return {"status": "error", "message": "Failed to send disarm command"}

        except Exception as e:
            logger.error(f"Disarm command failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _takeoff(self, altitude: float) -> Dict:
        """Take off to specified altitude."""
        try:
            takeoff_msg = {
                "type": "COMMAND_LONG",
                "param1": 0,
                "param2": 0,
                "param3": 0,
                "param4": 0,
                "param5": 0,  # lat
                "param6": 0,  # lon
                "param7": altitude,  # alt
                "command": 22,  # MAV_CMD_NAV_TAKEOFF
                "target_system": 1,
                "target_component": 1,
            }

            success = await self.runtime.protocol_adapter.send(takeoff_msg)
            if success:
                logger.info(f"Takeoff command sent to {altitude}m")
                await self.runtime.event_system.publish("autopilot.takeoff", altitude=altitude)
                return {"status": "success", "message": f"Takeoff to {altitude}m commanded"}
            else:
                return {"status": "error", "message": "Failed to send takeoff command"}

        except Exception as e:
            logger.error(f"Takeoff command failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _land(self) -> Dict:
        """Land the vehicle."""
        try:
            land_msg = {
                "type": "COMMAND_LONG",
                "param1": 0,
                "param2": 0,
                "param3": 0,
                "param4": 0,
                "param5": 0,  # lat
                "param6": 0,  # lon
                "param7": 0,  # alt
                "command": 21,  # MAV_CMD_NAV_LAND
                "target_system": 1,
                "target_component": 1,
            }

            success = await self.runtime.protocol_adapter.send(land_msg)
            if success:
                logger.info("Land command sent")
                await self.runtime.event_system.publish("autopilot.landing")
                return {"status": "success", "message": "Land command sent"}
            else:
                return {"status": "error", "message": "Failed to send land command"}

        except Exception as e:
            logger.error(f"Land command failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _goto_location(self, lat: float, lon: float, alt: float) -> Dict:
        """Navigate to specific location."""
        try:
            goto_msg = {
                "type": "COMMAND_LONG",
                "param1": 0,
                "param2": 0,
                "param3": 0,
                "param4": 0,
                "param5": lat * 1e7,  # Convert to int32 format
                "param6": lon * 1e7,
                "param7": alt,
                "command": 16,  # MAV_CMD_NAV_WAYPOINT
                "target_system": 1,
                "target_component": 1,
            }

            success = await self.runtime.protocol_adapter.send(goto_msg)
            if success:
                logger.info(f"Goto command sent: {lat}, {lon}, {alt}")
                await self.runtime.event_system.publish("autopilot.goto",
                    lat=lat, lon=lon, alt=alt)
                return {"status": "success", "message": f"Navigating to {lat}, {lon}, {alt}"}
            else:
                return {"status": "error", "message": "Failed to send goto command"}

        except Exception as e:
            logger.error(f"Goto command failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _set_mode(self, mode: str) -> Dict:
        """Set vehicle flight mode."""
        try:
            # Map string mode to MAVLink mode number
            mode_map = {
                "STABILIZE": 0,
                "ACRO": 1,
                "ALT_HOLD": 2,
                "AUTO": 3,
                "GUIDED": 4,
                "LOITER": 5,
                "RTL": 6,
                "CIRCLE": 7,
                "LAND": 9,
                "DRIFT": 11,
                "SPORT": 13,
                "FLIP": 14,
                "AUTOTUNE": 15,
                "POSHOLD": 16,
                "BRAKE": 17,
            }

            mode_num = mode_map.get(mode.upper())
            if mode_num is None:
                return {"status": "error", "message": f"Unknown mode: {mode}"}

            mode_msg = {
                "type": "COMMAND_LONG",
                "param1": mode_num,
                "param2": 0,
                "param3": 0,
                "param4": 0,
                "param5": 0,
                "param6": 0,
                "param7": 0,
                "command": 176,  # MAV_CMD_DO_SET_MODE
                "target_system": 1,
                "target_component": 1,
            }

            success = await self.runtime.protocol_adapter.send(mode_msg)
            if success:
                logger.info(f"Mode set to: {mode}")
                await self.runtime.event_system.publish("autopilot.mode_changed", mode=mode)
                return {"status": "success", "message": f"Mode set to {mode}"}
            else:
                return {"status": "error", "message": "Failed to set mode"}

        except Exception as e:
            logger.error(f"Set mode failed: {e}")
            return {"status": "error", "message": str(e)}

    def _get_status(self) -> Dict:
        """Get autopilot status."""
        state = self.runtime.state.get()
        return {
            "armed": state.armed,
            "mode": state.mode,
            "position": {
                "lat": state.lat,
                "lon": state.lon,
                "alt": state.alt
            }
        }

    async def _on_mission_event(self, event):
        """Handle mission events."""
        event_type = event.name

        if event_type == "mission.started":
            # Switch to GUIDED mode for mission
            await self._set_mode("GUIDED")
            await asyncio.sleep(0.5)  # Wait for mode change

            # Take off if not already airborne
            state = self.runtime.state.get()
            if state.relative_alt < 1.0:  # Ground level
                await self._takeoff(self.config.get("takeoff_altitude", 10.0))

        elif event_type == "mission.next_waypoint":
            # Navigate to next waypoint
            wp = event.waypoint
            await self._goto_location(wp["lat"], wp["lon"], wp["alt"])

        elif event_type == "mission.completed":
            # Return to launch or land
            await self._set_mode("RTL")

        elif event_type == "mission.stopped":
            # Emergency stop - land immediately
            await self._land()

    async def _on_heartbeat(self, event):
        """Handle heartbeat messages."""
        msg = event.msg
        mode = getattr(msg, "custom_mode", None)
        armed = bool(getattr(msg, "base_mode", 0) & 0x80)

        # Update state
        self.runtime.state.update(armed=armed, mode=str(mode))