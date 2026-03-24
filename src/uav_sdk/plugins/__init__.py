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
]
