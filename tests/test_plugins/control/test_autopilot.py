"""
Tests for autopilot plugin.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from uav_sdk.plugins.control.autopilot import AutopilotPlugin


class TestAutopilotPlugin:
    """Test autopilot functionality."""

    @pytest.fixture
    def mock_runtime(self):
        """Create mock runtime."""
        runtime = Mock()
        runtime.event_system = Mock()
        runtime.event_system.publish = AsyncMock()
        runtime.state = Mock()
        runtime.state.get = Mock()
        runtime.protocol_adapter = Mock()
        runtime.protocol_adapter.send = AsyncMock(return_value=True)
        return runtime

    @pytest.fixture
    def plugin(self, mock_runtime):
        """Create plugin instance."""
        config = {"takeoff_altitude": 10.0, "auto_arm": False}
        return AutopilotPlugin(config, mock_runtime)

    @pytest.mark.asyncio
    async def test_initialization(self, plugin, mock_runtime):
        """Test plugin initialization."""
        success = await plugin.initialize()
        assert success
        assert plugin.state.value == "initialized"

    @pytest.mark.asyncio
    async def test_arm_vehicle(self, plugin, mock_runtime):
        """Test vehicle arming."""
        await plugin.initialize()

        result = await plugin.process({"command": "arm"})

        assert result["status"] == "success"
        assert "Arm command sent" in result["message"]

        # Check MAVLink message sent
        mock_runtime.protocol_adapter.send.assert_called_once()
        call_args = mock_runtime.protocol_adapter.send.call_args[0][0]
        assert call_args["type"] == "COMMAND_LONG"
        assert call_args["command"] == 400  # MAV_CMD_COMPONENT_ARM_DISARM
        assert call_args["param1"] == 1  # ARM

    @pytest.mark.asyncio
    async def test_disarm_vehicle(self, plugin, mock_runtime):
        """Test vehicle disarming."""
        await plugin.initialize()

        result = await plugin.process({"command": "disarm"})

        assert result["status"] == "success"
        assert "Disarm command sent" in result["message"]

        # Check MAVLink message sent
        mock_runtime.protocol_adapter.send.assert_called_once()
        call_args = mock_runtime.protocol_adapter.send.call_args[0][0]
        assert call_args["type"] == "COMMAND_LONG"
        assert call_args["command"] == 400  # MAV_CMD_COMPONENT_ARM_DISARM
        assert call_args["param1"] == 0  # DISARM

    @pytest.mark.asyncio
    async def test_takeoff(self, plugin, mock_runtime):
        """Test takeoff command."""
        await plugin.initialize()

        result = await plugin.process({"command": "takeoff", "altitude": 15.0})

        assert result["status"] == "success"
        assert "15.0m" in result["message"]

        # Check MAVLink message sent
        mock_runtime.protocol_adapter.send.assert_called_once()
        call_args = mock_runtime.protocol_adapter.send.call_args[0][0]
        assert call_args["type"] == "COMMAND_LONG"
        assert call_args["command"] == 22  # MAV_CMD_NAV_TAKEOFF
        assert call_args["param7"] == 15.0

    @pytest.mark.asyncio
    async def test_land(self, plugin, mock_runtime):
        """Test land command."""
        await plugin.initialize()

        result = await plugin.process({"command": "land"})

        assert result["status"] == "success"
        assert "Land command sent" in result["message"]

        # Check MAVLink message sent
        mock_runtime.protocol_adapter.send.assert_called_once()
        call_args = mock_runtime.protocol_adapter.send.call_args[0][0]
        assert call_args["type"] == "COMMAND_LONG"
        assert call_args["command"] == 21  # MAV_CMD_NAV_LAND

    @pytest.mark.asyncio
    async def test_goto_location(self, plugin, mock_runtime):
        """Test goto location command."""
        await plugin.initialize()

        lat, lon, alt = 37.7749, -122.4194, 20.0
        result = await plugin.process({
            "command": "goto",
            "lat": lat,
            "lon": lon,
            "alt": alt
        })

        assert result["status"] == "success"
        assert f"{lat}, {lon}, {alt}" in result["message"]

        # Check MAVLink message sent
        mock_runtime.protocol_adapter.send.assert_called_once()
        call_args = mock_runtime.protocol_adapter.send.call_args[0][0]
        assert call_args["type"] == "COMMAND_LONG"
        assert call_args["command"] == 16  # MAV_CMD_NAV_WAYPOINT
        assert call_args["param5"] == lat * 1e7  # MAVLink int32 format
        assert call_args["param6"] == lon * 1e7
        assert call_args["param7"] == alt

    @pytest.mark.asyncio
    async def test_set_mode(self, plugin, mock_runtime):
        """Test mode setting."""
        await plugin.initialize()

        result = await plugin.process({"command": "set_mode", "mode": "GUIDED"})

        assert result["status"] == "success"
        assert "GUIDED" in result["message"]

        # Check MAVLink message sent
        mock_runtime.protocol_adapter.send.assert_called_once()
        call_args = mock_runtime.protocol_adapter.send.call_args[0][0]
        assert call_args["type"] == "COMMAND_LONG"
        assert call_args["command"] == 176  # MAV_CMD_DO_SET_MODE
        assert call_args["param1"] == 4  # GUIDED mode

    @pytest.mark.asyncio
    async def test_set_invalid_mode(self, plugin):
        """Test setting invalid mode."""
        await plugin.initialize()

        result = await plugin.process({"command": "set_mode", "mode": "INVALID"})

        assert result["status"] == "error"
        assert "Unknown mode" in result["message"]

    @pytest.mark.asyncio
    async def test_get_status(self, plugin, mock_runtime):
        """Test getting autopilot status."""
        await plugin.initialize()

        # Mock state
        mock_state = Mock()
        mock_state.armed = True
        mock_state.mode = "GUIDED"
        mock_state.lat = 37.7749
        mock_state.lon = -122.4194
        mock_state.alt = 20.0
        mock_runtime.state.get.return_value = mock_state

        result = await plugin.process({"command": "get_status"})

        assert result["armed"] == True
        assert result["mode"] == "GUIDED"
        assert result["position"]["lat"] == 37.7749
        assert result["position"]["lon"] == -122.4194
        assert result["position"]["alt"] == 20.0

    @pytest.mark.asyncio
    async def test_mission_started_event(self, plugin, mock_runtime):
        """Test handling mission started event."""
        await plugin.initialize()
        await plugin.start()

        # Mock mission started event
        mock_event = Mock()
        mock_event.name = "mission.started"

        # Mock state for ground check
        mock_state = Mock()
        mock_state.relative_alt = 0.5  # Below 1.0, should takeoff
        mock_runtime.state.get.return_value = mock_state

        await plugin._on_mission_event(mock_event)

        # Should have set mode to GUIDED and sent takeoff
        assert mock_runtime.protocol_adapter.send.call_count >= 2  # mode + takeoff

    @pytest.mark.asyncio
    async def test_next_waypoint_event(self, plugin, mock_runtime):
        """Test handling next waypoint event."""
        await plugin.initialize()

        # Mock next waypoint event
        mock_event = Mock()
        mock_event.name = "mission.next_waypoint"
        mock_event.waypoint = {"lat": 37.7749, "lon": -122.4194, "alt": 20.0}

        await plugin._on_mission_event(mock_event)

        # Should have sent goto command
        mock_runtime.protocol_adapter.send.assert_called_once()
        call_args = mock_runtime.protocol_adapter.send.call_args[0][0]
        assert call_args["command"] == 16  # MAV_CMD_NAV_WAYPOINT

    @pytest.mark.asyncio
    async def test_heartbeat_processing(self, plugin, mock_runtime):
        """Test heartbeat message processing."""
        await plugin.initialize()

        # Mock heartbeat message
        mock_msg = Mock()
        mock_msg.custom_mode = 4  # GUIDED
        mock_msg.base_mode = 0x80 | 0x40  # Armed + other flags

        mock_event = Mock()
        mock_event.msg = mock_msg

        await plugin._on_heartbeat(mock_event)

        # Should update state
        mock_runtime.state.update.assert_called_once_with(armed=True, mode="4")