"""
Base plugin classes for UAV SDK plugin system.

All plugins must inherit from one of these base classes.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import asyncio
import logging

logger = logging.getLogger(__name__)


class PluginState(Enum):
    """Plugin lifecycle states."""
    UNINITIALIZED = "uninitialized"
    INITIALIZED = "initialized"
    STARTED = "started"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class PluginInfo:
    """Metadata about a plugin."""
    name: str
    version: str
    author: str
    description: str
    plugin_type: str  # flight, perception, coordination, planning, protocol, driver
    dependencies: List[str] = field(default_factory=list)
    features: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)


class Plugin(ABC):
    """Abstract base class for all plugins.
    
    All plugin implementations must inherit from this class and implement
    the abstract methods.
    """
    
    def __init__(self, config: Dict[str, Any], runtime: 'SDKRuntime'):
        """Initialize plugin.
        
        Args:
            config: Plugin configuration dictionary
            runtime: SDK runtime instance for accessing services
        """
        self.config = config
        self.runtime = runtime
        self.state = PluginState.UNINITIALIZED
        self._info: Optional[PluginInfo] = None
        logger.debug(f"Plugin instance created: {self.__class__.__name__}")
    
    @abstractmethod
    def get_info(self) -> PluginInfo:
        """Return plugin metadata.
        
        Must be implemented by each plugin subclass.
        
        Returns:
            PluginInfo with name, version, dependencies, etc.
        """
        pass
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize plugin (load models, setup connections).
        
        Called once after plugin is loaded before start().
        Should set self.state to INITIALIZED on success.
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def start(self) -> bool:
        """Start plugin (begin processing/control loops).
        
        Called when plugin should become active.
        Should set self.state to STARTED on success.
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    async def pause(self) -> bool:
        """Pause execution without shutdown.
        
        Default implementation pauses state.
        Override for custom pause behavior.
        
        Returns:
            True if successful
        """
        self.state = PluginState.PAUSED
        logger.info(f"Plugin paused: {self.get_info().name}")
        return True
    
    async def resume(self) -> bool:
        """Resume from pause.
        
        Default implementation resumes state.
        Override for custom resume behavior.
        
        Returns:
            True if successful
        """
        self.state = PluginState.STARTED
        logger.info(f"Plugin resumed: {self.get_info().name}")
        return True
    
    @abstractmethod
    async def shutdown(self) -> bool:
        """Clean shutdown - release all resources.
        
        Called when plugin needs to stop.
        Opposite of initialize().
        
        Returns:
            True if successful
        """
        pass
    
    def get_diagnostics(self) -> Dict[str, Any]:
        """Return health/performance metrics.
        
        Override to provide plugin-specific diagnostics.
        
        Returns:
            Dictionary with diagnostic information
        """
        info = self.get_info()
        return {
            "name": info.name,
            "version": info.version,
            "state": self.state.value,
            "timestamp": asyncio.get_event_loop().time(),
        }
    
    def get_dependencies(self) -> List[str]:
        """Return list of required plugin names.
        
        Returns:
            List of plugin names this plugin depends on
        """
        return self.get_info().dependencies
    
    # Event subscription helpers
    def subscribe(self, event_name: str, callback):
        """Subscribe to event.
        
        Args:
            event_name: Event name (e.g., "sys.armed")
            callback: Async callback function
        """
        if hasattr(self.runtime, 'event_system'):
            self.runtime.event_system.subscribe(event_name, callback)
    
    def publish(self, event_name: str, **kwargs):
        """Publish event.
        
        Args:
            event_name: Event name (e.g., "mission.waypoint_reached")
            **kwargs: Event payload
        """
        if hasattr(self.runtime, 'event_system'):
            self.runtime.event_system.publish(event_name, **kwargs)
    
    # Configuration helpers
    def get_config(self, key: str, default=None):
        """Get configuration value.
        
        Args:
            key: Config key
            default: Default value if key not found
            
        Returns:
            Config value or default
        """
        return self.config.get(key, default)


class ProtocolPlugin(Plugin):
    """Base class for communication protocol plugins.
    
    Implement this for protocols like MAVLink, ROS2, etc.
    """
    
    @abstractmethod
    async def send_message(self, msg: Any) -> bool:
        """Send message to vehicle.
        
        Args:
            msg: Message to send
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    async def receive_message(self) -> Optional[Any]:
        """Receive message from vehicle.
        
        Returns:
            Received message or None if no message available
        """
        pass


class DriverPlugin(Plugin):
    """Base class for hardware driver plugins.
    
    Implement this for hardware interfaces like cameras, sensors, etc.
    """
    
    @abstractmethod
    async def read_sensor(self, sensor_id: str) -> Any:
        """Read data from sensor.
        
        Args:
            sensor_id: Sensor identifier
            
        Returns:
            Sensor reading data
        """
        pass
    
    @abstractmethod
    async def write_actuator(self, actuator_id: str, value: Any) -> bool:
        """Write command to actuator.
        
        Args:
            actuator_id: Actuator identifier
            value: Command value
            
        Returns:
            True if successful
        """
        pass


class ComputePlugin(Plugin):
    """Base class for compute-heavy plugins.
    
    Implement this for perception, planning, estimation, etc.
    """
    
    @abstractmethod
    async def process(self, input_data: Any) -> Any:
        """Process input data.
        
        Args:
            input_data: Input data to process
            
        Returns:
            Processing result
        """
        pass
