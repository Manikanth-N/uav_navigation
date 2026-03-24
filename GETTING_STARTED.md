# UAV SDK v2.0 - Getting Started Implementation

This guide walks you through setting up and beginning Phase 1 of the v2.0 migration.

## Quick Setup

### Step 1: Prepare Development Environment

```bash
# Clone/navigate to project
cd /home/manikanth/projects/uav_navigation

# Create virtual environment for v2.0 development
python3.10 -m venv venv_v2
source venv_v2/bin/activate

# Install development dependencies
pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"
```

### Step 2: Update pyproject.toml for v2.0

```toml
[project]
name = "uav_sdk"
version = "2.0.0a1"  # Alpha version during development
description = "Universal UAV onboard computation SDK with plugin architecture"
authors = [{name = "Manikanth"}]

dependencies = [
    "pymavlink>=2.4.0",
    "pyyaml>=6.0",
    "jsonschema>=4.0",
    "uvloop>=0.17.0",  # Fast async
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.20.0",
    "pytest-cov>=4.0",
    "black>=23.0",
    "pylint>=2.17.0",
    "mypy>=1.0",
    "sphinx>=5.0",
]

perception = [
    "opencv-python>=4.5.0",
    "numpy>=1.20.0",
]

plotting = ["matplotlib>=3.5"]
testing = ["gazebo-sim>=11.0"]  # Simulator integration
```

### Step 3: Directory Structure for v2.0

```
uav_navigation/
├── ARCHITECTURE.md          # ← Start here
├── PLUGIN_SYSTEM.md         # ← Plugin development guide
├── ROADMAP.md               # ← Implementation phases
├── COMPETITIVE_ADVANTAGES.md
├── pyproject.toml           # ← Updated
├── src/
│   └── uav_sdk/
│       ├── __init__.py      # Main exports
│       ├── version.py       # Version info
│       ├── core/            # Runtime core
│       │   ├── __init__.py
│       │   ├── sdk.py                    # Main SDK runtime
│       │   ├── types.py                  # Core data types
│       │   ├── state.py                  # State management (REFACT)
│       │   ├── event_system.py           # Pub/Sub (REFACT)
│       │   ├── lifecycle.py              # Lifecycle mgmt
│       │   ├── scheduler.py              # Task scheduling
│       │   └── logger.py                 # Logging
│       │
│       ├── plugins/         # Plugin system (NEW)
│       │   ├── __init__.py
│       │   ├── base.py                   # Abstract base classes
│       │   ├── manifest.py               # Manifest loader
│       │   ├── loader.py                 # Plugin discovery
│       │   ├── manager.py                # Lifecycle manager
│       │   └── registry.py               # DI container
│       │
│       ├── protocols/       # Protocol abstraction (NEW)
│       │   ├── __init__.py
│       │   ├── base.py                   # Abstract protocol
│       │   ├── mavlink.py                # MAVLink plugin
│       │   ├── ros2.py                   # ROS2 plugin
│       │   └── bridge.py                 # Multi-protocol bridge
│       │
│       ├── drivers/         # Hardware drivers (NEW)
│       │   ├── __init__.py
│       │   └── base.py                   # Driver base classes
│       │
│       ├── config/          # Configuration (NEW)
│       │   ├── __init__.py
│       │   ├── loader.py                 # Config loading
│       │   ├── schema.py                 # Schema validation
│       │   └── defaults.yaml             # Default configs
│       │
│       ├── logging/         # Observability (NEW)
│       │   ├── __init__.py
│       │   ├── logger.py                 # Structured logging
│       │   └── metrics.py                # Metrics collection
│       │
│       └── utils/           # Existing utilities
│           ├── __init__.py
│           ├── math.py
│           └── ...
│
├── plugins/                 # Plugin directory (NEW)
│   ├── builtin/             # Built-in plugins
│   │   ├── flight_controller/
│   │   │   ├── plugin.yaml
│   │   │   └── src/
│   │   ├── navigation/
│   │   │   ├── plugin.yaml
│   │   │   └── src/
│   │   └── ...
│   │
│   └── examples/            # Example user plugins
│       ├── custom_detector/
│       │   ├── plugin.yaml
│       │   └── src/
│       └── ...
│
├── tests/                   # Test suite
│   ├── test_plugins/        # Plugin system tests
│   ├── test_protocols/      # Protocol tests
│   ├── test_core/           # Core runtime tests
│   └── integration/         # Integration tests
│
└── examples/                # User-facing examples
    ├── basic_flight.py      # Simple flight example
    ├── custom_plugin.py     # Plugin creation example
    └── multi_vehicle.py     # Swarm control example
```

---

## Phase 1 Implementation Steps

### 1.1 Create Core Plugin System Foundation

**File**: `src/uav_sdk/plugins/base.py`

See `PLUGIN_SYSTEM.md` for complete implementation.

**Quick Start**:
```bash
# Create plugin module
mkdir -p src/uav_sdk/plugins

# Copy template from PLUGIN_SYSTEM.md
nano src/uav_sdk/plugins/base.py         # Implement Plugin classes
nano src/uav_sdk/plugins/manifest.py     # Manifest loader
nano src/uav_sdk/plugins/loader.py       # Plugin loader
nano src/uav_sdk/plugins/manager.py      # Lifecycle manager
```

### 1.2 Create Core Runtime

**File**: `src/uav_sdk/core/sdk.py`

```python
"""Main SDK runtime"""
import asyncio
import logging
from typing import Dict, Optional
from pathlib import Path

from .state import UAVState
from .event_system import EventSystem
from .scheduler import Scheduler
from .logger import Logger
from ..plugins.manager import PluginManager
from ..plugins.loader import PluginLoader

logger = logging.getLogger(__name__)

class UAVDriver:
    """Main SDK class - entry point for users"""
    
    def __init__(self, 
                 config_path: Optional[str] = None,
                 plugin_dirs: Optional[list] = None):
        
        # Core services
        self.state = UAVState()
        self.event_system = EventSystem()
        self.scheduler = Scheduler()
        self.logger = Logger()
        
        # Plugin infrastructure
        self.plugin_dirs = plugin_dirs or ["./plugins"]
        self.plugin_loader = PluginLoader(self.plugin_dirs)
        self.plugin_manager = PluginManager(
            self.plugin_loader.registry, 
            self
        )
        
        # Configuration
        self.config = self._load_config(config_path)
        
        logger.info("UAV SDK initialized")
    
    def _load_config(self, path: Optional[str]) -> Dict:
        """Load configuration from file or defaults"""
        if path:
            # Load from file
            pass
        else:
            # Return defaults
            return self._default_config()
    
    async def initialize(self) -> bool:
        """Initialize SDK and plugins"""
        logger.info("Initializing SDK...")
        
        # Load plugins
        if not await self.plugin_manager.instantiate_plugins(
            self.config.get("plugins", {})
        ):
            return False
        
        # Initialize plugins
        if not await self.plugin_manager.initialize_plugins():
            return False
        
        logger.info("SDK initialization complete")
        return True
    
    async def start(self) -> bool:
        """Start all plugins"""
        logger.info("Starting SDK...")
        
        if not await self.plugin_manager.start_plugins():
            return False
        
        logger.info("SDK started")
        return True
    
    async def shutdown(self) -> bool:
        """Shutdown SDK and plugins"""
        logger.info("Shutting down SDK...")
        
        if not await self.plugin_manager.shutdown_plugins():
            return False
        
        logger.info("SDK shutdown complete")
        return True
    
    def get_vehicle(self, name: str = "primary"):
        """Get vehicle interface"""
        # Return vehicle abstraction
        pass
    
    # Event system convenience methods
    def subscribe(self, event: str, callback):
        """Subscribe to event"""
        self.event_system.subscribe(event, callback)
    
    def publish(self, event: str, **kwargs):
        """Publish event"""
        self.event_system.publish(event, **kwargs)
    
    def _default_config(self) -> Dict:
        """Return default configuration"""
        return {
            "plugins": {
                # Default plugins to load
            }
        }

# Convenience factory
async def create_sdk(config_path: str = None) -> UAVDriver:
    """Create and initialize SDK"""
    sdk = UAVDriver(config_path)
    await sdk.initialize()
    return sdk
```

### 1.3 Update State Management

**File**: `src/uav_sdk/core/state.py`

```python
"""Thread-safe vehicle state management"""
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class VehicleState:
    """Current vehicle state snapshot"""
    # Position/orientation
    timestamp: float = 0.0
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0
    
    # Attitude
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    
    # Velocity
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    
    # Status
    armed: bool = False
    mode: str = "STABILIZE"
    battery_percent: float = 100.0
    
    # Custom fields from plugins
    custom: Dict[str, Any] = field(default_factory=dict)

class UAVState:
    """Thread-safe state management with MVCC"""
    
    def __init__(self):
        self._lock = threading.RLock()
        self._state = VehicleState()
        self._version = 0
        self._change_listeners: List[Callable] = []
        self._history: List[VehicleState] = []
        self._max_history = 100  # Keep last 100 states
    
    def get(self) -> VehicleState:
        """Get current state (thread-safe)"""
        with self._lock:
            return VehicleState(**vars(self._state))  # Return copy
    
    def update(self, **kwargs) -> int:
        """Update state fields, return version number"""
        with self._lock:
            # Update fields
            for key, value in kwargs.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)
            
            # Increment version
            self._version += 1
            
            # Keep history
            self._history.append(VehicleState(**vars(self._state)))
            if len(self._history) > self._max_history:
                self._history.pop(0)
            
            # Notify listeners
            for listener in self._change_listeners:
                listener(self._state)
            
            logger.debug(f"State updated (v{self._version}): {kwargs}")
            return self._version
    
    def subscribe(self, callback: Callable):
        """Subscribe to state changes"""
        with self._lock:
            self._change_listeners.append(callback)
    
    def get_version(self) -> int:
        """Get current state version"""
        with self._lock:
            return self._version
    
    def get_history(self, count: int = 10) -> List[VehicleState]:
        """Get last N state snapshots"""
        with self._lock:
            return self._history[-count:]
```

### 1.4 Create Test Suite

**File**: `tests/test_plugins/test_plugin_manager.py`

```python
"""Tests for plugin system"""
import pytest
import asyncio
import yaml
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from uav_sdk.plugins.base import Plugin, PluginState, PluginInfo
from uav_sdk.plugins.manager import PluginManager
from uav_sdk.plugins.loader import PluginRegistry

class MockPlugin(Plugin):
    """Mock plugin for testing"""
    
    def get_info(self):
        return PluginInfo(
            name="mock_plugin",
            version="1.0.0",
            author="Test",
            description="Test plugin",
            plugin_type="test",
            dependencies=[],
            features=[],
            config_schema={},
        )
    
    async def initialize(self):
        self.init_called = True
        return True
    
    async def start(self):
        self.start_called = True
        return True
    
    async def shutdown(self):
        return True

@pytest.mark.asyncio
async def test_plugin_initialization():
    """Test plugin lifecycle"""
    mock_runtime = Mock()
    plugin = MockPlugin({}, mock_runtime)
    
    assert await plugin.initialize()
    assert plugin.state == PluginState.INITIALIZED

@pytest.mark.asyncio
async def test_plugin_manager_dependency_resolution():
    """Test dependency sorting"""
    registry = PluginRegistry()
    manager = PluginManager(registry, Mock())
    
    # Test topological sort
    plugin_names = ["c", "b", "a"]  # Reverse order
    sorted_names = manager._resolve_dependencies(plugin_names)
    
    # At minimum, should not error
    assert sorted_names is not None

@pytest.mark.asyncio
async def test_plugin_lifecycle():
    """Test plugin lifecycle management"""
    registry = PluginRegistry()
    manager = PluginManager(registry, Mock())
    
    # Register mock plugin
    registry.register("mock", MockPlugin, MockPlugin({}, Mock()).get_info())
    
    # Instantiate
    config = {"mock": {}}
    assert await manager.instantiate_plugins(config, ["mock"])
    
    # Initialize
    assert await manager.initialize_plugins()
    
    # Start
    assert await manager.start_plugins()
    
    # Shutdown
    assert await manager.shutdown_plugins()
```

### 1.5 Create Example Configuration

**File**: `src/uav_sdk/config/default.yaml`

```yaml
# Default SDK configuration

sdk:
  debug: false
  log_level: INFO
  
plugins:
  # Core plugins - required
  event_system:
    enabled: true
    
  state_manager:
    enabled: true
    max_history: 100
  
  # Protocol plugins - at least one required
  mavlink:
    enabled: true
    connection_string: "tcp:127.0.0.1:5763"
    baudrate: 115200
    
  # Flight control plugin
  flight_controller:
    enabled: true
    control_loop_rate: 400  # Hz
    pid_gains:
      roll: {p: 4.5, i: 0.1, d: 0.15}
      pitch: {p: 4.5, i: 0.1, d: 0.15}
      yaw: {p: 6.0, i: 0.1, d: 0.3}
  
  # Optional perception plugin
  perception:
    enabled: false
    camera_id: 0
    fps: 30

logging:
  level: INFO
  format: json  # or "human"
  file: "logs/uav_sdk.log"
  max_size_mb: 100
  backup_count: 5
```

---

## Running Phase 1

### Setup & Install

```bash
# Install in development mode
cd /home/manikanth/projects/uav_navigation
pip install -e ".[dev]"

# Run tests
pytest tests/ -v --cov=src/uav_sdk
```

### Create Basic Example

**File**: `examples/basic_flight.py`

```python
#!/usr/bin/env python3
"""
Basic UAV SDK v2.0 example
- Connect to vehicle
- Arm & takeoff
- Land
"""

import asyncio
import logging
from uav_sdk.core.sdk import UAVDriver

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Create SDK
    sdk = UAVDriver(config_path="src/uav_sdk/config/default.yaml")
    
    # Initialize
    if not await sdk.initialize():
        logger.error("Failed to initialize SDK")
        return
    
    # Start plugins
    if not await sdk.start():
        logger.error("Failed to start SDK")
        return
    
    try:
        # Get vehicle
        uav = sdk.get_vehicle()
        
        # Arm
        logger.info("Arming...")
        await uav.arm()
        
        # Takeoff
        logger.info("Taking off...")
        await uav.takeoff(altitude=10.0)
        
        # Hold for 30 seconds
        await asyncio.sleep(30)
        
        # Land
        logger.info("Landing...")
        await uav.land()
        
        logger.info("Mission complete!")
        
    finally:
        await sdk.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

### Run Example

```bash
python examples/basic_flight.py
```

---

## Checkpoint: End of Phase 1

By the end of Phase 1, you should have:

- ✅ Working plugin system (load/instantiate/lifecycle)
- ✅ Refactored state & event systems
- ✅ Configuration management
- ✅ Logging & metrics infrastructure
- ✅ Basic examples
- ✅ >90% test coverage of core

**Validation**:
```bash
# Check code quality
pylint src/uav_sdk/ --exit-zero
mypy src/uav_sdk/ --ignore-missing-imports

# Run tests
pytest tests/ -v --cov=src/uav_sdk

# Build docs
sphinx-build -b html docs/ docs/_build/
```

---

## Next Steps

Once Phase 1 is complete:
1. Review ARCHITECTURE.md & ROADMAP.md
2. Begin Phase 2: Protocol abstraction
3. Involve community for feedback
4. Document lessons learned

See `ROADMAP.md` for full development plan.

