"""
Tests for plugin system infrastructure.
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock
from dataclasses import dataclass

# Assume installed in editable mode
from uav_sdk.plugins import (
    Plugin, PluginInfo, PluginState, PluginRegistry, 
    PluginLoader, PluginManager, ManifestLoader
)


# ============================================================================
# Mock Plugin Implementations
# ============================================================================

class MockPlugin(Plugin):
    """Simple mock plugin for testing."""
    
    def __init__(self, config, runtime):
        super().__init__(config, runtime)
        self.init_called = False
        self.start_called = False
        self.shutdown_called = False
    
    def get_info(self):
        return PluginInfo(
            name="mock_plugin",
            version="1.0.0",
            author="Test",
            description="Test mock plugin",
            plugin_type="test",
            dependencies=[],
            features=[],
            config_schema={},
        )
    
    async def initialize(self):
        self.init_called = True
        self.state = PluginState.INITIALIZED
        return True
    
    async def start(self):
        self.start_called = True
        self.state = PluginState.STARTED
        return True
    
    async def shutdown(self):
        self.shutdown_called = True
        self.state = PluginState.STOPPED
        return True


class MockDependentPlugin(Plugin):
    """Plugin with dependencies."""
    
    def get_info(self):
        return PluginInfo(
            name="dependent_plugin",
            version="1.0.0",
            author="Test",
            description="Test plugin with dependencies",
            plugin_type="test",
            dependencies=["mock_plugin"],
            features=[],
            config_schema={},
        )
    
    async def initialize(self):
        self.state = PluginState.INITIALIZED
        return True
    
    async def start(self):
        self.state = PluginState.STARTED
        return True
    
    async def shutdown(self):
        self.state = PluginState.STOPPED
        return True


# ============================================================================
# Plugin Base Class Tests
# ============================================================================

class TestPluginBase:
    """Tests for base Plugin class."""
    
    def test_plugin_initialization(self):
        """Test plugin can be initialized."""
        mock_runtime = Mock()
        plugin = MockPlugin({}, mock_runtime)
        
        assert plugin.state == PluginState.UNINITIALIZED
        assert plugin.config == {}
    
    @pytest.mark.asyncio
    async def test_plugin_lifecycle(self):
        """Test plugin lifecycle transitions."""
        mock_runtime = Mock()
        plugin = MockPlugin({}, mock_runtime)
        
        # Initialize
        assert await plugin.initialize()
        assert plugin.state == PluginState.INITIALIZED
        
        # Start
        assert await plugin.start()
        assert plugin.state == PluginState.STARTED
        
        # Pause
        assert await plugin.pause()
        assert plugin.state == PluginState.PAUSED
        
        # Resume
        assert await plugin.resume()
        assert plugin.state == PluginState.STARTED
        
        # Shutdown
        assert await plugin.shutdown()
    
    def test_plugin_info(self):
        """Test plugin info retrieval."""
        mock_runtime = Mock()
        plugin = MockPlugin({}, mock_runtime)
        
        info = plugin.get_info()
        assert info.name == "mock_plugin"
        assert info.version == "1.0.0"
        assert info.plugin_type == "test"
    
    def test_plugin_diagnostics(self):
        """Test plugin diagnostics."""
        mock_runtime = Mock()
        plugin = MockPlugin({}, mock_runtime)
        
        diag = plugin.get_diagnostics()
        assert diag["name"] == "mock_plugin"
        assert "state" in diag
        assert "timestamp" in diag


# ============================================================================
# Plugin Registry Tests
# ============================================================================

class TestPluginRegistry:
    """Tests for PluginRegistry."""
    
    def test_register_plugin(self):
        """Test plugin registration."""
        registry = PluginRegistry()
        info = PluginInfo(
            name="test", version="1.0", author="Test",
            description="Test", plugin_type="test",
            dependencies=[], features=[], config_schema={}
        )
        
        registry.register("test", MockPlugin, info)
        
        assert registry.is_registered("test")
        assert registry.get_plugin_class("test") == MockPlugin
        assert registry.get_manifest("test") == info
    
    def test_list_plugins(self):
        """Test listing registered plugins."""
        registry = PluginRegistry()
        info = PluginInfo(
            name="test", version="1.0", author="Test",
            description="Test", plugin_type="test",
            dependencies=[], features=[], config_schema={}
        )
        
        registry.register("test", MockPlugin, info)
        plugins = registry.list_plugins()
        
        assert len(plugins) == 1
        assert "test" in plugins


# ============================================================================
# Plugin Manager Tests
# ============================================================================

class TestPluginManager:
    """Tests for PluginManager."""
    
    def test_dependency_resolution_simple(self):
        """Test dependency resolution with simple case."""
        registry = PluginRegistry()
        
        # Register plugins
        manager = PluginManager(registry, Mock())
        
        info1 = PluginInfo(
            name="plugin_a", version="1.0", author="Test",
            description="Test", plugin_type="test",
            dependencies=[], features=[], config_schema={}
        )
        info2 = PluginInfo(
            name="plugin_b", version="1.0", author="Test",
            description="Test", plugin_type="test",
            dependencies=["plugin_a"], features=[], config_schema={}
        )
        
        registry.register("plugin_a", MockPlugin, info1)
        registry.register("plugin_b", MockDependentPlugin, info2)
        
        # Resolve
        order = manager._resolve_dependencies(["plugin_a", "plugin_b"])
        
        assert order is not None
        assert order.index("plugin_a") < order.index("plugin_b")
    
    def test_circular_dependency_detection(self):
        """Test circular dependency detection."""
        registry = PluginRegistry()
        manager = PluginManager(registry, Mock())
        
        # Create circular dependency: a->b, b->a
        info_a = PluginInfo(
            name="plugin_a", version="1.0", author="T",
            description="", plugin_type="test",
            dependencies=["plugin_b"], features=[], config_schema={}
        )
        info_b = PluginInfo(
            name="plugin_b", version="1.0", author="T",
            description="", plugin_type="test",
            dependencies=["plugin_a"], features=[], config_schema={}
        )
        
        registry.register("plugin_a", MockPlugin, info_a)
        registry.register("plugin_b", MockDependentPlugin, info_b)
        
        # Should detect cycle
        order = manager._resolve_dependencies(["plugin_a", "plugin_b"])
        assert order is None
    
    @pytest.mark.asyncio
    async def test_plugin_instantiation(self):
        """Test plugin instantiation."""
        registry = PluginRegistry()
        mock_runtime = Mock()
        manager = PluginManager(registry, mock_runtime)
        
        info = PluginInfo(
            name="test", version="1.0", author="Test",
            description="Test", plugin_type="test",
            dependencies=[], features=[], config_schema={}
        )
        registry.register("test", MockPlugin, info)
        
        config = {"test": {"param": "value"}}
        assert await manager.instantiate_plugins(config)
        
        plugin = manager.get_plugin("test")
        assert plugin is not None
    
    @pytest.mark.asyncio
    async def test_plugin_lifecycle_manager(self):
        """Test plugin lifecycle through manager."""
        registry = PluginRegistry()
        mock_runtime = Mock()
        manager = PluginManager(registry, mock_runtime)
        
        info = PluginInfo(
            name="test", version="1.0", author="Test",
            description="Test", plugin_type="test",
            dependencies=[], features=[], config_schema={}
        )
        registry.register("test", MockPlugin, info)
        
        config = {"test": {}}
        
        # Full lifecycle
        assert await manager.instantiate_plugins(config)
        assert await manager.initialize_plugins()
        assert await manager.start_plugins()
        assert await manager.shutdown_plugins()
        
        # Check state transitions
        plugin = manager.get_plugin("test")
        assert plugin.init_called
        assert plugin.start_called
        assert plugin.shutdown_called


# ============================================================================
# Manifest Tests
# ============================================================================

class TestManifestLoader:
    """Tests for ManifestLoader."""
    
    def test_manifest_validation(self):
        """Test manifest validation."""
        # Valid manifest
        manifest = ManifestLoader.load(
            Path(__file__).parent / "fixtures" / "plugin.yaml"
        )
        # Should not raise
        assert manifest is not None


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
