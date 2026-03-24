"""
Tests for mission planner plugin.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from uav_sdk.plugins.navigation.mission_planner import MissionPlannerPlugin, Waypoint


class TestMissionPlannerPlugin:
    """Test mission planner functionality."""

    @pytest.fixture
    def mock_runtime(self):
        """Create mock runtime."""
        runtime = Mock()
        runtime.event_system = Mock()
        runtime.event_system.publish = AsyncMock()
        runtime.state = Mock()
        runtime.state.update = Mock()
        return runtime

    @pytest.fixture
    def plugin(self, mock_runtime):
        """Create plugin instance."""
        config = {"default_speed": 5.0, "reached_threshold": 1.0}
        return MissionPlannerPlugin(config, mock_runtime)

    @pytest.mark.asyncio
    async def test_initialization(self, plugin, mock_runtime):
        """Test plugin initialization."""
        success = await plugin.initialize()
        assert success
        assert plugin.state.value == "initialized"

        # Check state update
        mock_runtime.state.update.assert_called_with(
            mission_waypoints=[],
            mission_current_index=-1,
            mission_active=False
        )

    @pytest.mark.asyncio
    async def test_load_mission(self, plugin, mock_runtime):
        """Test mission loading."""
        await plugin.initialize()

        waypoints_data = [
            {"lat": 37.7749, "lon": -122.4194, "alt": 20.0},
            {"lat": 37.7849, "lon": -122.4094, "alt": 25.0},
        ]

        result = await plugin.process({"command": "load_mission", "waypoints": waypoints_data})

        assert result["status"] == "success"
        assert result["waypoint_count"] == 2
        assert len(plugin.waypoints) == 2

        # Check first waypoint
        wp = plugin.waypoints[0]
        assert wp.lat == 37.7749
        assert wp.lon == -122.4194
        assert wp.alt == 20.0
        assert wp.speed == 5.0  # default

    @pytest.mark.asyncio
    async def test_start_mission(self, plugin, mock_runtime):
        """Test mission start."""
        await plugin.initialize()

        # Load mission first
        waypoints_data = [{"lat": 37.7749, "lon": -122.4194, "alt": 20.0}]
        await plugin.process({"command": "load_mission", "waypoints": waypoints_data})

        # Start mission
        result = await plugin.process({"command": "start_mission"})

        assert result["status"] == "success"
        assert plugin.mission_active
        assert plugin.current_waypoint_index == 0

        # Check state update
        mock_runtime.state.update.assert_called_with(mission_active=True, mission_current_index=0)

    @pytest.mark.asyncio
    async def test_start_mission_no_waypoints(self, plugin):
        """Test starting mission without waypoints."""
        await plugin.initialize()

        result = await plugin.process({"command": "start_mission"})

        assert result["status"] == "error"
        assert "No mission loaded" in result["message"]

    @pytest.mark.asyncio
    async def test_get_status(self, plugin):
        """Test getting mission status."""
        await plugin.initialize()

        status = await plugin.process({"command": "get_status"})

        assert status["active"] == False
        assert status["current_waypoint"] == -1
        assert status["total_waypoints"] == 0
        assert status["waypoints"] == []

    @pytest.mark.asyncio
    async def test_position_update_waypoint_reached(self, plugin, mock_runtime):
        """Test waypoint reached detection."""
        await plugin.initialize()

        # Load mission
        waypoints_data = [{"lat": 37.7749, "lon": -122.4194, "alt": 20.0, "hold_time": 0.1}]
        await plugin.process({"command": "load_mission", "waypoints": waypoints_data})
        await plugin.process({"command": "start_mission"})

        # Simulate position update at waypoint
        mock_msg = Mock()
        mock_msg.lat = int(37.7749 * 1e7)  # Convert to MAVLink format
        mock_msg.lon = int(-122.4194 * 1e7)
        mock_msg.alt = 20 * 1000  # mm

        mock_event = Mock()
        mock_event.msg = mock_msg

        # Call position update
        await plugin._on_position_update(mock_event)

        # Should have reached waypoint and completed mission
        assert plugin.current_waypoint_index == -1  # Mission completed, reset to -1
        assert not plugin.mission_active  # Mission completed

        # Check events published
        assert mock_runtime.event_system.publish.call_count >= 2  # waypoint_reached + mission.completed

    def test_distance_calculation(self, plugin):
        """Test distance calculation between waypoints."""
        # Same point
        dist = plugin._calculate_distance(37.7749, -122.4194, 20.0, 37.7749, -122.4194, 20.0)
        assert dist == 0.0

        # 1 degree latitude difference (approx 111km)
        dist = plugin._calculate_distance(37.7749, -122.4194, 20.0, 38.7749, -122.4194, 20.0)
        assert abs(dist - 111000) < 1000  # Within 1km

        # Altitude difference
        dist = plugin._calculate_distance(37.7749, -122.4194, 20.0, 37.7749, -122.4194, 30.0)
        assert dist == 10.0

    @pytest.mark.asyncio
    async def test_stop_mission(self, plugin, mock_runtime):
        """Test mission stop."""
        await plugin.initialize()

        # Load and start mission
        waypoints_data = [{"lat": 37.7749, "lon": -122.4194, "alt": 20.0}]
        await plugin.process({"command": "load_mission", "waypoints": waypoints_data})
        await plugin.process({"command": "start_mission"})

        # Stop mission
        result = await plugin.process({"command": "stop_mission"})

        assert result["status"] == "success"
        assert not plugin.mission_active
        assert plugin.current_waypoint_index == -1