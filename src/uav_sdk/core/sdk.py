"""
Main UAV SDK runtime.

Entry point for users - provides access to all SDK services
and manages plugin lifecycle.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .state import UAVState
from .event_system import EventSystem
from .version import __version__
from ..config import ConfigManager, get_default_config
from ..logging import StructuredLogger, MetricsCollector
from ..plugins import PluginLoader, PluginManager

logger = logging.getLogger(__name__)


class UAVDriver:
    """Main SDK class - entry point for users.
    
    Provides access to:
    - Plugin system
    - State management
    - Event system
    - Configuration
    - Logging & metrics
    """
    
    def __init__(self, 
                 config_path: Optional[str] = None,
                 plugin_dirs: Optional[List[str]] = None,
                 log_level: str = "INFO"):
        """Initialize SDK.
        
        Args:
            config_path: Path to configuration file (YAML/JSON)
            plugin_dirs: List of directories to search for plugins
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        # Create core services
        self.state = UAVState()
        self.event_system = EventSystem()
        
        # Configuration
        self.config = ConfigManager()
        self.config.merge(get_default_config())
        
        if config_path:
            self.config.load_file(config_path)
        
        # Logging
        self.logger = StructuredLogger("uav_sdk", log_level)
        self.metrics = MetricsCollector()
        
        # Plugin system
        self.plugin_dirs = plugin_dirs or ["./plugins"]
        self.plugin_loader = PluginLoader(self.plugin_dirs)
        self.plugin_manager = PluginManager(
            self.plugin_loader.registry,
            self
        )

        # Protocol adapter (MAVLink, ROS2, etc.)
        self.protocol_adapter = None

        self._initialized = False
        self._started = False
        
        logger.info(f"UAV SDK v{__version__} initialized")
    
    async def initialize(self) -> bool:
        """Initialize SDK and discover plugins.
        
        Should be called before start(). Discovers plugins in plugin
        directories and loads them.
        
        Returns:
            True if successful
        """
        logger.info("Initializing SDK...")
        
        # Discover plugins
        discovered = self.plugin_loader.discover()
        logger.info(f"Discovered {len(discovered)} plugins in plugin directories")
        
        # Get plugins to load from config (only those actually discovered)
        plugin_config = self.config.get("plugins", {})
        plugin_names = [
            name for name, cfg in plugin_config.items()
            if cfg.get("enabled", True) and name in discovered
        ]
        
        logger.info(f"Loading {len(plugin_names)} enabled plugins")
        
        # Load plugins
        if plugin_names:
            if not self.plugin_loader.load_all(plugin_names):
                logger.warning("Some plugins failed to load")
        
        # Instantiate plugins
        if plugin_names:
            if not await self.plugin_manager.instantiate_plugins(
                plugin_config,
                plugin_names
            ):
                logger.error("Failed to instantiate plugins")
                return False
            
            # Initialize plugins
            if not await self.plugin_manager.initialize_plugins():
                logger.error("Failed to initialize plugins")
                return False
        
        self._initialized = True
        logger.info("SDK initialization complete")
        return True
    
    async def start(self) -> bool:
        """Start all loaded plugins.
        
        Calls start() on each plugin in dependency order.
        
        Returns:
            True if successful
        """
        if not self._initialized:
            logger.error("SDK not initialized. Call initialize() first.")
            return False
        
        logger.info("Starting SDK...")
        
        if not await self.plugin_manager.start_plugins():
            logger.error("Failed to start plugins")
            return False
        
        self._started = True
        logger.info("SDK started successfully")
        return True
    
    async def shutdown(self) -> bool:
        """Shutdown SDK and all plugins.
        
        Gracefully stops all plugins in reverse order.
        
        Returns:
            True if successful
        """
        logger.info("Shutting down SDK...")
        
        if self._started:
            if not await self.plugin_manager.shutdown_plugins():
                logger.error("Errors during plugin shutdown")
                return False
        
        self._started = False
        self._initialized = False
        logger.info("SDK shutdown complete")
        return True
    
    def get_plugin(self, name: str):
        """Get a loaded plugin by name.
        
        Args:
            name: Plugin name
            
        Returns:
            Plugin instance or None if not found
        """
        return self.plugin_manager.get_plugin(name)
    
    def list_loaded_plugins(self) -> Dict:
        """List all loaded plugins.
        
        Returns:
            Dictionary mapping plugin names to instances
        """
        return self.plugin_manager.list_loaded_plugins()

    def set_protocol_adapter(self, adapter):
        """Set a protocol adapter for the SDK.
        
        Args:
            adapter: Instance implementing ProtocolInterface
        """
        self.protocol_adapter = adapter

    async def connect_protocol(self) -> bool:
        """Connect protocol adapter if configured."""
        if self.protocol_adapter is None:
            logger.error("No protocol adapter configured")
            return False
        return await self.protocol_adapter.connect()

    async def disconnect_protocol(self) -> bool:
        """Disconnect protocol adapter if configured."""
        if self.protocol_adapter is None:
            logger.error("No protocol adapter configured")
            return False
        return await self.protocol_adapter.disconnect()

    async def send_protocol_message(self, msg) -> bool:
        """Send a message through protocol adapter."""
        if self.protocol_adapter is None:
            logger.error("No protocol adapter configured")
            return False
        return await self.protocol_adapter.send(msg)

    async def receive_protocol_message(self, timeout: float = 0.1):
        """Receive a message from protocol adapter."""
        if self.protocol_adapter is None:
            logger.error("No protocol adapter configured")
            return None
        return await self.protocol_adapter.receive(timeout)

    # Convenience methods for event system
    def subscribe(self, event_name: str, callback):
        """Subscribe to an event.
        
        Args:
            event_name: Event name
            callback: Callback function
        """
        self.event_system.subscribe(event_name, callback)
    
    async def publish(self, event_name: str, **kwargs):
        """Publish an event.
        
        Args:
            event_name: Event name
            **kwargs: Event payload
        """
        await self.event_system.publish(event_name, **kwargs)
    
    def is_initialized(self) -> bool:
        """Check if SDK is initialized.
        
        Returns:
            True if initialized
        """
        return self._initialized
    
    def is_started(self) -> bool:
        """Check if SDK is running.
        
        Returns:
            True if started
        """
        return self._started


# Factory function for convenience
async def create_sdk(
    config_path: Optional[str] = None,
    plugin_dirs: Optional[List[str]] = None
) -> UAVDriver:
    """Create and initialize SDK.
    
    Convenience factory that creates and initializes SDK in one call.
    
    Args:
        config_path: Path to config file
        plugin_dirs: Plugin search directories
        
    Returns:
        Initialized UAVDriver
    """
    sdk = UAVDriver(config_path, plugin_dirs)
    if not await sdk.initialize():
        raise RuntimeError("Failed to initialize SDK")
    return sdk
