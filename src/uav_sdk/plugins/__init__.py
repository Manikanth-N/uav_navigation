"""
UAV SDK Plugin System

Provides plugin architecture for extensible SDK components.
"""

from .base import (
    Plugin,
    ProtocolPlugin,
    DriverPlugin,
    ComputePlugin,
    PluginState,
    PluginInfo,
)
from .loader import PluginLoader
from .manager import PluginManager
from .registry import PluginRegistry
from .manifest import ManifestLoader, PluginManifest
from .mavlink_plugin import MavlinkProtocolPlugin
from .navigation.mission_planner import MissionPlannerPlugin
from .control.autopilot import AutopilotPlugin
from .perception.camera import CameraPlugin
from .perception.object_detection import ObjectDetectionPlugin
from .perception.depth_sensor import DepthSensorPlugin
from .perception.sensor_fusion import SensorFusionPlugin

__all__ = [
    "Plugin",
    "ProtocolPlugin",
    "DriverPlugin",
    "ComputePlugin",
    "PluginState",
    "PluginInfo",
    "PluginLoader",
    "PluginManager",
    "PluginRegistry",
    "ManifestLoader",
    "PluginManifest",
    "MavlinkProtocolPlugin",
]
