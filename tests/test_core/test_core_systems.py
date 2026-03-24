"""
Tests for core SDK components (state, events, config).
"""

import pytest
import asyncio

from uav_sdk.core.state import VehicleState, UAVState
from uav_sdk.core.event_system import EventSystem
from uav_sdk.config.loader import ConfigManager, get_default_config


# ============================================================================
# State Management Tests
# ============================================================================

class TestVehicleState:
    """Tests for VehicleState data class."""
    
    def test_default_state(self):
        """Test default state values."""
        state = VehicleState()
        
        assert state.lat == 0.0
        assert state.lon == 0.0
        assert state.alt == 0.0
        assert state.armed == False
        assert state.battery_percent == 100.0
    
    def test_state_modification(self):
        """Test state field modification."""
        state = VehicleState()
        state.lat = 37.7749
        state.lon = -122.4194
        state.alt = 100.0
        
        assert state.lat == 37.7749
        assert state.lon == -122.4194
        assert state.alt == 100.0


class TestUAVState:
    """Tests for UAVState thread-safe state manager."""
    
    def test_state_get(self):
        """Test getting state."""
        uav_state = UAVState()
        state = uav_state.get()
        
        assert isinstance(state, VehicleState)
        assert state.armed == False
    
    def test_state_update(self):
        """Test updating state."""
        uav_state = UAVState()
        
        v1 = uav_state.update(lat=37.7749, lon=-122.4194, armed=True)
        assert v1 == 1
        
        state = uav_state.get()
        assert state.lat == 37.7749
        assert state.lon == -122.4194
        assert state.armed == True
    
    def test_state_versioning(self):
        """Test state versioning."""
        uav_state = UAVState()
        
        v1 = uav_state.update(lat=1.0)
        v2 = uav_state.update(lon=2.0)
        v3 = uav_state.update(alt=3.0)
        
        assert v1 < v2 < v3
        assert uav_state.get_version() == 3
    
    def test_state_history(self):
        """Test state history."""
        uav_state = UAVState()
        
        uav_state.update(lat=1.0)
        uav_state.update(lat=2.0)
        uav_state.update(lat=3.0)
        
        history = uav_state.get_history(count=2)
        assert len(history) == 2
    
    def test_state_subscription(self):
        """Test state change subscription."""
        uav_state = UAVState()
        
        changes = []
        def callback(state):
            changes.append(state.lat)
        
        uav_state.subscribe(callback)
        uav_state.update(lat=1.0)
        uav_state.update(lat=2.0)
        
        assert changes == [1.0, 2.0]
    
    def test_state_helpers(self):
        """Test state helper methods."""
        uav_state = UAVState()
        
        uav_state.update(lat=37.7749, lon=-122.4194, alt=100.0)
        
        assert uav_state.are_gps_coordinates_valid()
        
        pos = uav_state.get_position_tuple()
        assert pos == (37.7749, -122.4194, 100.0)
    
    def test_state_reset(self):
        """Test state reset."""
        uav_state = UAVState()
        
        uav_state.update(lat=37.7749, lon=-122.4194, armed=True)
        uav_state.reset()
        
        state = uav_state.get()
        assert state.lat == 0.0
        assert state.lon == 0.0
        assert state.armed == False


# ============================================================================
# Event System Tests
# ============================================================================

class TestEventSystem:
    """Tests for EventSystem pub/sub."""
    
    @pytest.mark.asyncio
    async def test_event_publish_subscribe(self):
        """Test basic pub/sub."""
        events = EventSystem()
        received = []
        
        async def callback(event):
            received.append(event)
        
        events.subscribe("test.event", callback)
        await events.publish("test.event", data="hello")
        
        await asyncio.sleep(0.01)  # Give async time to execute
        
        assert len(received) == 1
        assert received[0].name == "test.event"
        assert received[0].payload["data"] == "hello"
    
    @pytest.mark.asyncio
    async def test_event_wildcard(self):
        """Test wildcard subscriptions."""
        events = EventSystem()
        received = []
        
        async def callback(event):
            received.append(event.name)
        
        events.subscribe("sys.*", callback)
        await events.publish("sys.armed")
        await events.publish("sys.mode_changed")
        await events.publish("other.event")
        
        await asyncio.sleep(0.01)
        
        assert len(received) == 2
        assert "sys.armed" in received
        assert "sys.mode_changed" in received
    
    @pytest.mark.asyncio
    async def test_event_history(self):
        """Test event history."""
        events = EventSystem()
        
        await events.publish("test", a=1)
        await events.publish("test", a=2)
        await events.publish("other", b=3)
        
        history = events.get_history("test", count=10)
        assert len(history) == 2
    
    def test_event_unsubscribe(self):
        """Test unsubscribing."""
        events = EventSystem()
        
        def callback(e):
            pass
        
        events.subscribe("test", callback)
        assert events.unsubscribe("test", callback)
        assert not events.unsubscribe("test", callback)


# ============================================================================
# Configuration Tests
# ============================================================================

class TestConfigManager:
    """Tests for ConfigManager."""
    
    def test_config_set_get(self):
        """Test setting and getting config."""
        config = ConfigManager()
        
        config.set("app.name", "MyApp")
        config.set("app.version", "1.0.0")
        
        assert config.get("app.name") == "MyApp"
        assert config.get("app.version") == "1.0.0"
    
    def test_config_dot_notation(self):
        """Test dot notation paths."""
        config = ConfigManager()
        
        config.set("database.postgres.host", "localhost")
        config.set("database.postgres.port", 5432)
        
        assert config.get("database.postgres.host") == "localhost"
        assert config.get("database.postgres.port") == 5432
    
    def test_config_defaults(self):
        """Test default values."""
        config = ConfigManager()
        
        assert config.get("nonexistent", "default") == "default"
        assert config.get("nonexistent") is None
    
    def test_config_merge(self):
        """Test merging configs."""
        config = ConfigManager()
        config.set("a", 1)
        
        config.merge({"b": 2, "c": 3})
        
        assert config.get("a") == 1
        assert config.get("b") == 2
        assert config.get("c") == 3
    
    def test_default_config(self):
        """Test default SDK config."""
        defaults = get_default_config()
        
        assert "sdk" in defaults
        assert "plugins" in defaults
        assert "logging" in defaults


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
