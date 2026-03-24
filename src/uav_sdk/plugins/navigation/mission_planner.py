"""
Mission planning plugin for UAV navigation.

Manages waypoints, mission execution, and path planning.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import math
import asyncio
import logging

from uav_sdk.plugins.base import ComputePlugin, PluginInfo, PluginState

logger = logging.getLogger(__name__)


@dataclass
class Waypoint:
    """Represents a mission waypoint."""
    lat: float
    lon: float
    alt: float
    speed: float = 5.0  # m/s
    hold_time: float = 0.0  # seconds to hold at waypoint
    reached_threshold: float = 1.0  # meters


class MissionPlannerPlugin(ComputePlugin):
    """Mission planning and waypoint management plugin."""

    def __init__(self, config: Dict[str, Any], runtime):
        super().__init__(config, runtime)
        self.waypoints: List[Waypoint] = []
        self.current_waypoint_index: int = -1
        self.mission_active: bool = False
        self._position_callback = None

    def get_info(self):
        return PluginInfo(
            name="mission_planner",
            version="0.1.0",
            author="SDK Team",
            description="Mission planning and waypoint navigation",
            plugin_type="navigation",
            dependencies=["mavlink_protocol"],
            features=["waypoint_navigation", "mission_planning"],
            config_schema={
                "default_speed": {"type": "number", "default": 5.0},
                "reached_threshold": {"type": "number", "default": 1.0},
            },
        )

    async def initialize(self) -> bool:
        # Subscribe to position updates
        self._position_callback = self._on_position_update
        self.subscribe("mavlink.GLOBAL_POSITION_INT", self._position_callback)

        # Update state with mission fields
        self.runtime.state.update(
            mission_waypoints=[],
            mission_current_index=-1,
            mission_active=False
        )

        self.state = PluginState.INITIALIZED
        logger.info("Mission planner initialized")
        return True

    async def start(self) -> bool:
        self.state = PluginState.STARTED
        logger.info("Mission planner started")
        return True

    async def shutdown(self) -> bool:
        if self._position_callback:
            # Note: unsubscribe not implemented in base class yet
            pass
        self.state = PluginState.STOPPED
        logger.info("Mission planner shutdown")
        return True

    async def process(self, input_data: Any) -> Any:
        """Process mission planning requests."""
        if isinstance(input_data, dict):
            command = input_data.get("command")
            if command == "load_mission":
                return await self._load_mission(input_data.get("waypoints", []))
            elif command == "start_mission":
                return await self._start_mission()
            elif command == "pause_mission":
                return await self._pause_mission()
            elif command == "resume_mission":
                return await self._resume_mission()
            elif command == "stop_mission":
                return await self._stop_mission()
            elif command == "get_status":
                return self._get_mission_status()

        return {"error": "Unknown command"}

    async def _load_mission(self, waypoints_data: List[Dict]) -> Dict:
        """Load waypoints into mission."""
        try:
            self.waypoints = []
            for wp_data in waypoints_data:
                wp = Waypoint(
                    lat=wp_data["lat"],
                    lon=wp_data["lon"],
                    alt=wp_data["alt"],
                    speed=wp_data.get("speed", self.config.get("default_speed", 5.0)),
                    hold_time=wp_data.get("hold_time", 0.0),
                    reached_threshold=wp_data.get("threshold", self.config.get("reached_threshold", 1.0))
                )
                self.waypoints.append(wp)

            # Update state
            self.runtime.state.update(
                mission_waypoints=[{
                    "lat": wp.lat, "lon": wp.lon, "alt": wp.alt,
                    "speed": wp.speed, "hold_time": wp.hold_time
                } for wp in self.waypoints]
            )

            logger.info(f"Loaded mission with {len(self.waypoints)} waypoints")
            await self.runtime.event_system.publish("mission.loaded", waypoint_count=len(self.waypoints))
            return {"status": "success", "waypoint_count": len(self.waypoints)}

        except Exception as e:
            logger.error(f"Failed to load mission: {e}")
            return {"status": "error", "message": str(e)}

    async def _start_mission(self) -> Dict:
        """Start mission execution."""
        if not self.waypoints:
            return {"status": "error", "message": "No mission loaded"}

        self.mission_active = True
        self.current_waypoint_index = 0
        self.runtime.state.update(mission_active=True, mission_current_index=0)

        logger.info("Mission started")
        await self.runtime.event_system.publish("mission.started", waypoint_count=len(self.waypoints))
        return {"status": "success"}

    async def _pause_mission(self) -> Dict:
        """Pause mission execution."""
        self.mission_active = False
        self.runtime.state.update(mission_active=False)
        await self.runtime.event_system.publish("mission.paused")
        return {"status": "success"}

    async def _resume_mission(self) -> Dict:
        """Resume mission execution."""
        if self.waypoints and self.current_waypoint_index >= 0:
            self.mission_active = True
            self.runtime.state.update(mission_active=True)
            await self.runtime.event_system.publish("mission.resumed")
            return {"status": "success"}
        return {"status": "error", "message": "No mission to resume"}

    async def _stop_mission(self) -> Dict:
        """Stop mission execution."""
        self.mission_active = False
        self.current_waypoint_index = -1
        self.runtime.state.update(mission_active=False, mission_current_index=-1)
        await self.runtime.event_system.publish("mission.stopped")
        return {"status": "success"}

    def _get_mission_status(self) -> Dict:
        """Get current mission status."""
        return {
            "active": self.mission_active,
            "current_waypoint": self.current_waypoint_index,
            "total_waypoints": len(self.waypoints),
            "waypoints": [{
                "lat": wp.lat, "lon": wp.lon, "alt": wp.alt,
                "speed": wp.speed, "hold_time": wp.hold_time
            } for wp in self.waypoints] if self.waypoints else []
        }

    async def _on_position_update(self, event):
        """Handle position updates from MAVLink."""
        if not self.mission_active or not self.waypoints:
            return

        msg = event.msg
        current_lat = getattr(msg, "lat", 0) / 1e7  # Convert from int32 degrees * 1e7
        current_lon = getattr(msg, "lon", 0) / 1e7
        current_alt = getattr(msg, "alt", 0) / 1000.0  # Convert from mm to meters

        # Update state position
        self.runtime.state.update(lat=current_lat, lon=current_lon, alt=current_alt)

        # Check if current waypoint reached
        if self.current_waypoint_index < len(self.waypoints):
            current_wp = self.waypoints[self.current_waypoint_index]
            distance = self._calculate_distance(
                current_lat, current_lon, current_alt,
                current_wp.lat, current_wp.lon, current_wp.alt
            )

            if distance <= current_wp.reached_threshold:
                await self._on_waypoint_reached(current_wp)

    def _calculate_distance(self, lat1, lon1, alt1, lat2, lon2, alt2) -> float:
        """Calculate 3D distance between two points."""
        # Haversine distance for lat/lon
        R = 6371000  # Earth radius in meters
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        horizontal_distance = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        # Vertical distance
        vertical_distance = abs(alt2 - alt1)

        # 3D distance
        return math.sqrt(horizontal_distance**2 + vertical_distance**2)

    async def _on_waypoint_reached(self, waypoint: Waypoint):
        """Handle waypoint reached event."""
        logger.info(f"Waypoint reached: {self.current_waypoint_index + 1}/{len(self.waypoints)}")

        # Publish waypoint reached event
        await self.runtime.event_system.publish("mission.waypoint_reached",
            index=self.current_waypoint_index,
            waypoint={"lat": waypoint.lat, "lon": waypoint.lon, "alt": waypoint.alt}
        )

        # Handle hold time
        if waypoint.hold_time > 0:
            await asyncio.sleep(waypoint.hold_time)

        # Move to next waypoint
        self.current_waypoint_index += 1
        self.runtime.state.update(mission_current_index=self.current_waypoint_index)

        if self.current_waypoint_index >= len(self.waypoints):
            # Mission complete
            await self._stop_mission()
            await self.runtime.event_system.publish("mission.completed")
            logger.info("Mission completed")
        else:
            # Publish next waypoint
            next_wp = self.waypoints[self.current_waypoint_index]
            await self.runtime.event_system.publish("mission.next_waypoint",
                index=self.current_waypoint_index,
                waypoint={"lat": next_wp.lat, "lon": next_wp.lon, "alt": next_wp.alt, "speed": next_wp.speed}
            )