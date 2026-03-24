# Plugin System - Implementation Guide

## Overview
This document provides detailed implementation guidance for the UAV SDK v2.0 plugin system.

## 1. Core Plugin Infrastructure

### 1.1 Plugin Base Classes

**File**: `src/uav_sdk/plugins/base.py`

```python
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import asyncio

class PluginState(Enum):
    """Plugin lifecycle states"""
    UNINITIALIZED = "uninitialized"
    INITIALIZED = "initialized"
    STARTED = "started"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"

@dataclass
class PluginInfo:
    """Metadata about a plugin"""
    name: str
    version: str
    author: str
    description: str
    plugin_type: str  # flight, perception, coordination, planning, protocol, driver
    dependencies: List[str]
    features: List[str]
    config_schema: Dict[str, Any]

class Plugin(ABC):
    """Abstract base class for all plugins"""
    
    def __init__(self, config: Dict[str, Any], runtime: 'SDKRuntime'):
        self.config = config
        self.runtime = runtime
        self.state = PluginState.UNINITIALIZED
        self._info: Optional[PluginInfo] = None
        self._loop = asyncio.get_event_loop()
    
    @abstractmethod
    def get_info(self) -> PluginInfo:
        """Return plugin metadata - implemented by each plugin"""
        pass
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize plugin (load models, setup connections)
        Called once after plugin is loaded
        """
        pass
    
    @abstractmethod
    async def start(self) -> bool:
        """
        Start plugin (begin processing/control loops)
        Called when plugin should become active
        """
        pass
    
    async def pause(self) -> bool:
        """Pause execution without shutdown"""
        self.state = PluginState.PAUSED
        return True
    
    async def resume(self) -> bool:
        """Resume from pause"""
        self.state = PluginState.STARTED
        return True
    
    @abstractmethod
    async def shutdown(self) -> bool:
        """Clean shutdown - release all resources"""
        pass
    
    def get_diagnostics(self) -> Dict[str, Any]:
        """Return health/performance metrics"""
        return {
            "name": self.get_info().name,
            "state": self.state.value,
            "timestamp": asyncio.get_event_loop().time(),
        }
    
    def get_dependencies(self) -> List[str]:
        """Return list of required plugins"""
        return self.get_info().dependencies
    
    # Event subscription helpers
    def subscribe(self, event_name: str, callback):
        """Subscribe to event"""
        self.runtime.event_system.subscribe(event_name, callback)
    
    def publish(self, event_name: str, **kwargs):
        """Publish event"""
        self.runtime.event_system.publish(event_name, **kwargs)
    
    # Configuration helpers
    def get_config(self, key: str, default=None):
        """Get config value"""
        return self.config.get(key, default)

class ProtocolPlugin(Plugin):
    """Base class for communication protocol plugins"""
    
    @abstractmethod
    async def send_message(self, msg: Any) -> bool:
        """Send message to vehicle"""
        pass
    
    @abstractmethod
    async def receive_message(self) -> Optional[Any]:
        """Receive message from vehicle"""
        pass

class DriverPlugin(Plugin):
    """Base class for hardware driver plugins"""
    
    @abstractmethod
    async def read_sensor(self, sensor_id: str) -> Any:
        """Read data from sensor"""
        pass
    
    @abstractmethod
    async def write_actuator(self, actuator_id: str, value: Any) -> bool:
        """Write command to actuator"""
        pass

class ComputePlugin(Plugin):
    """Base class for compute-heavy plugins (perception, planning, etc)"""
    
    @abstractmethod
    async def process(self, input_data: Any) -> Any:
        """Process input data"""
        pass
```

### 1.2 Plugin Manifest Loader

**File**: `src/uav_sdk/plugins/manifest.py`

```python
import yaml
import json
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class PluginManifest:
    """Parsed plugin manifest"""
    name: str
    version: str
    author: str
    description: str
    plugin_type: str
    category: str
    dependencies: Dict[str, str]  # {name: version_spec}
    entry_point: str  # module.path:ClassName
    config_schema: Dict
    features: list
    tags: list
    platforms: list
    min_memory_mb: int
    python_version: str

class ManifestLoader:
    @staticmethod
    def load(path: Path) -> PluginManifest:
        """Load and parse plugin.yaml"""
        with open(path) as f:
            if path.suffix == '.yaml':
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
        
        return PluginManifest(
            name=data['name'],
            version=data['version'],
            author=data['author'],
            description=data['description'],
            plugin_type=data['type'],
            category=data.get('category', 'general'),
            dependencies=data.get('dependencies', {}),
            entry_point=data['entry_point'],
            config_schema=data.get('config', {}),
            features=data.get('features', []),
            tags=data.get('tags', []),
            platforms=data.get('platforms', []),
            min_memory_mb=data.get('min_memory_mb', 1),
            python_version=data.get('python_version', '>=3.8'),
        )
```

### 1.3 Plugin Loader & Registry

**File**: `src/uav_sdk/plugins/loader.py`

```python
import importlib
import sys
from pathlib import Path
from typing import Dict, Optional, Type
import logging

from .manifest import ManifestLoader, PluginManifest
from .base import Plugin

logger = logging.getLogger(__name__)

class PluginRegistry:
    """Central registry of all loaded plugins"""
    
    def __init__(self):
        self._plugins: Dict[str, Type[Plugin]] = {}
        self._manifests: Dict[str, PluginManifest] = {}
    
    def register(self, name: str, plugin_class: Type[Plugin], 
                 manifest: PluginManifest):
        """Register a plugin"""
        self._plugins[name] = plugin_class
        self._manifests[name] = manifest
    
    def get_plugin_class(self, name: str) -> Optional[Type[Plugin]]:
        """Get plugin class by name"""
        return self._plugins.get(name)
    
    def get_manifest(self, name: str) -> Optional[PluginManifest]:
        """Get plugin manifest by name"""
        return self._manifests.get(name)
    
    def list_plugins(self) -> Dict[str, PluginManifest]:
        """List all registered plugins"""
        return self._manifests.copy()

class PluginLoader:
    """Discovers and loads plugins"""
    
    def __init__(self, plugin_dirs: list):
        self.plugin_dirs = [Path(d) for d in plugin_dirs]
        self.registry = PluginRegistry()
    
    def discover(self) -> Dict[str, PluginManifest]:
        """Discover all available plugins"""
        discovered = {}
        
        for plugin_dir in self.plugin_dirs:
            for manifest_file in plugin_dir.glob('*/plugin.yaml'):
                try:
                    manifest = ManifestLoader.load(manifest_file)
                    discovered[manifest.name] = manifest
                    logger.info(f"Discovered plugin: {manifest.name} v{manifest.version}")
                except Exception as e:
                    logger.error(f"Failed to load manifest {manifest_file}: {e}")
        
        return discovered
    
    def load_plugin(self, name: str, manifest: PluginManifest) -> bool:
        """Load a specific plugin"""
        try:
            module_path, class_name = manifest.entry_point.split(':')
            
            # Import module dynamically
            module = importlib.import_module(module_path)
            plugin_class = getattr(module, class_name)
            
            # Validate it's a Plugin subclass
            if not issubclass(plugin_class, Plugin):
                logger.error(f"{name}: {class_name} is not a Plugin subclass")
                return False
            
            # Register
            self.registry.register(name, plugin_class, manifest)
            logger.info(f"Loaded plugin: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load plugin {name}: {e}")
            return False
    
    def load_all(self) -> bool:
        """Load all discovered plugins"""
        manifests = self.discover()
        
        for name, manifest in manifests.items():
            self.load_plugin(name, manifest)
        
        return True
```

### 1.4 Plugin Manager (Lifecycle & Dependency Resolution)

**File**: `src/uav_sdk/plugins/manager.py`

```python
import asyncio
from typing import Dict, List, Optional
from collections import defaultdict
import logging

from .base import Plugin, PluginState
from .loader import PluginRegistry

logger = logging.getLogger(__name__)

class PluginManager:
    """Manages plugin lifecycle and dependency resolution"""
    
    def __init__(self, registry: PluginRegistry, runtime):
        self.registry = registry
        self.runtime = runtime
        self._instances: Dict[str, Plugin] = {}
        self._load_order: List[str] = []
    
    async def instantiate_plugins(self, config: Dict[str, Dict], 
                                  plugin_names: Optional[List[str]] = None) -> bool:
        """
        Create plugin instances and resolve dependencies
        
        Args:
            config: {plugin_name: plugin_config}
            plugin_names: specific plugins to load (None = all)
        """
        
        # Resolve load order via topological sort
        load_order = self._resolve_dependencies(plugin_names)
        if load_order is None:
            logger.error("Circular dependency detected in plugins")
            return False
        
        self._load_order = load_order
        
        # Instantiate plugins in dependency order
        for plugin_name in load_order:
            manifest = self.registry.get_manifest(plugin_name)
            plugin_class = self.registry.get_plugin_class(plugin_name)
            
            if not plugin_class:
                logger.error(f"Plugin class not found: {plugin_name}")
                return False
            
            plugin_config = config.get(plugin_name, {})
            
            try:
                instance = plugin_class(plugin_config, self.runtime)
                self._instances[plugin_name] = instance
                logger.info(f"Instantiated plugin: {plugin_name}")
            except Exception as e:
                logger.error(f"Failed to instantiate {plugin_name}: {e}")
                return False
        
        return True
    
    async def initialize_plugins(self) -> bool:
        """Initialize all plugins in dependency order"""
        for plugin_name in self._load_order:
            plugin = self._instances[plugin_name]
            
            try:
                success = await plugin.initialize()
                if success:
                    plugin.state = PluginState.INITIALIZED
                    logger.info(f"Initialized: {plugin_name}")
                else:
                    logger.error(f"Plugin initialization failed: {plugin_name}")
                    return False
            except Exception as e:
                logger.error(f"Error initializing {plugin_name}: {e}")
                return False
        
        return True
    
    async def start_plugins(self) -> bool:
        """Start all plugins in dependency order"""
        for plugin_name in self._load_order:
            plugin = self._instances[plugin_name]
            
            try:
                success = await plugin.start()
                if success:
                    plugin.state = PluginState.STARTED
                    logger.info(f"Started: {plugin_name}")
                else:
                    logger.error(f"Plugin start failed: {plugin_name}")
                    return False
            except Exception as e:
                logger.error(f"Error starting {plugin_name}: {e}")
                return False
        
        return True
    
    async def shutdown_plugins(self) -> bool:
        """Shutdown all plugins in reverse order"""
        errors = []
        
        # Reverse order for cleanup
        for plugin_name in reversed(self._load_order):
            plugin = self._instances[plugin_name]
            
            try:
                success = await plugin.shutdown()
                if success:
                    plugin.state = PluginState.STOPPED
                    logger.info(f"Shutdown: {plugin_name}")
                else:
                    errors.append(plugin_name)
            except Exception as e:
                logger.error(f"Error shutting down {plugin_name}: {e}")
                errors.append(plugin_name)
        
        return len(errors) == 0
    
    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get plugin instance by name"""
        return self._instances.get(name)
    
    def _resolve_dependencies(self, plugin_names: Optional[List[str]] = None) 
                             -> Optional[List[str]]:
        """Topological sort to resolve plugin dependencies"""
        
        if plugin_names is None:
            plugin_names = list(self.registry.list_plugins().keys())
        
        # Build dependency graph
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        
        for name in plugin_names:
            if name not in in_degree:
                in_degree[name] = 0
            
            manifest = self.registry.get_manifest(name)
            for dep_name in manifest.dependencies.keys():
                if dep_name in plugin_names:
                    graph[dep_name].append(name)
                    in_degree[name] += 1
        
        # Kahn's algorithm for topological sort
        queue = [n for n in plugin_names if in_degree[n] == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # Check for cycles
        if len(result) != len(plugin_names):
            return None  # Circular dependency
        
        return result
```

## 2. Example: Creating a Custom Plugin

### Example: Custom Vision Detection Plugin

**File structure**:
```
my_detector_plugin/
├── plugin.yaml
├── src/
│   ├── __init__.py
│   └── detector.py
└── models/
    └── model.onnx
```

**plugin.yaml**:
```yaml
name: custom_detector
version: 1.0.0
author: Your Name
description: "Custom YOLO-based object detector"

type: perception
category: detection

dependencies:
  - name: event_system
    version: ">=1.0.0"

entry_point: src.detector:CustomDetectorPlugin

config:
  type: object
  properties:
    model_path: {type: string, default: "models/model.onnx"}
    confidence_threshold: {type: number, default: 0.5}
    camera_id: {type: integer, default: 0}
    inference_rate: {type: integer, default: 30}

features: [object-detection, yolo, custom]
tags: [perception, ai]
platforms: [arm64, x86_64]
min_memory_mb: 500
python_version: ">=3.8"
```

**src/detector.py**:
```python
import asyncio
import logging
from typing import Dict, Any, Optional
import cv2
import numpy as np

from uav_sdk.plugins import ComputePlugin, PluginInfo

logger = logging.getLogger(__name__)

class CustomDetectorPlugin(ComputePlugin):
    """Custom object detection plugin"""
    
    def __init__(self, config: Dict[str, Any], runtime):
        super().__init__(config, runtime)
        self.detector = None
        self.camera = None
        self.processing = False
    
    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="custom_detector",
            version="1.0.0",
            author="Your Name",
            description="Custom YOLO-based object detector",
            plugin_type="perception",
            dependencies=["event_system"],
            features=["object-detection", "yolo"],
            config_schema=self.config,
        )
    
    async def initialize(self) -> bool:
        """Load model and setup"""
        try:
            model_path = self.get_config("model_path")
            # Load ONNX model (pseudo-code)
            self.detector = self._load_model(model_path)
            logger.info("Detector model loaded")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize detector: {e}")
            return False
    
    async def start(self) -> bool:
        """Start processing loop"""
        self.processing = True
        
        # Start background processing task
        asyncio.create_task(self._process_loop())
        
        logger.info("Detector started")
        return True
    
    async def _process_loop(self):
        """Main processing loop"""
        rate = self.get_config("inference_rate")
        interval = 1.0 / rate
        
        while self.processing:
            # Get frame from camera
            frame = await self._get_camera_frame()
            
            if frame is not None:
                # Run inference
                detections = self.detector.infer(frame)
                
                # Publish results
                self.publish("perception.detections_available", 
                           detections=detections,
                           timestamp=asyncio.get_event_loop().time())
            
            await asyncio.sleep(interval)
    
    async def _get_camera_frame(self):
        """Get frame from camera"""
        # In real implementation, interface with camera driver
        pass
    
    async def process(self, input_data: np.ndarray) -> Dict[str, Any]:
        """Process a single frame"""
        return self.detector.infer(input_data)
    
    async def shutdown(self) -> bool:
        """Stop and cleanup"""
        self.processing = False
        await asyncio.sleep(0.1)  # Let loop finish
        logger.info("Detector shutdown")
        return True
    
    def _load_model(self, path: str):
        """Load ONNX model"""
        # Pseudo-code for loading ONNX model
        import onnxruntime as ort
        return ort.InferenceSession(path)
```

## 3. Using Plugins in SDK Runtime

```python
from uav_sdk import UAVDriver
from uav_sdk.plugins import PluginLoader

# Setup
plugin_dirs = ["./plugins", "./extensions"]
loader = PluginLoader(plugin_dirs)

# Configuration
plugin_config = {
    "mavlink_protocol": {
        "connection_string": "tcp:127.0.0.1:5763"
    },
    "flight_controller": {
        "pid_gains": {"p": 1.5, "i": 0.2, "d": 0.8},
        "rate": 400
    },
    "custom_detector": {
        "model_path": "/opt/models/detector.onnx",
        "confidence_threshold": 0.6,
        "inference_rate": 30
    }
}

# Create and run SDK
async def main():
    sdk = UAVDriver()
    
    # Load plugins
    sdk.plugin_manager.loader = loader
    await sdk.plugin_manager.instantiate_plugins(plugin_config)
    await sdk.plugin_manager.initialize_plugins()
    await sdk.plugin_manager.start_plugins()
    
    # Use SDK normally - plugins run in background
    try:
        uav = sdk.get_vehicle_interface()
        await uav.arm()
        await uav.set_mode("GUIDED")
        
        # Listen to custom plugin events
        sdk.events.subscribe("perception.detections_available", 
                             on_detections)
        
        # Let everything run
        while True:
            await asyncio.sleep(1)
    
    finally:
        await sdk.plugin_manager.shutdown_plugins()

if __name__ == "__main__":
    asyncio.run(main())
```

## 4. Best Practices

1. **Single Responsibility**: Each plugin does one thing well
2. **Event-Driven**: Use pub/sub for plugin communication
3. **Async/Await**: Use asyncio for all I/O
4. **Type Hints**: Full type hints for IDE support
5. **Logging**: Use Python logging module
6. **Error Handling**: Graceful error handling and recovery
7. **Configuration**: Use YAML config, not hardcoding
8. **Testing**: Unit test each plugin independently
9. **Documentation**: Document config schema clearly
10. **Versioning**: Use SemVer for plugin versions

