"""
Plugin registry and dependency injection container.

Central registry of all loaded plugins with metadata.
"""

from typing import Dict, Optional, Type, List
import logging

from .base import Plugin
from .manifest import PluginManifest

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Central registry of all loaded plugins.
    
    Acts as a DI container for plugin instances and metadata.
    """
    
    def __init__(self):
        """Initialize empty registry."""
        self._plugin_classes: Dict[str, Type[Plugin]] = {}
        self._manifests: Dict[str, PluginManifest] = {}
    
    def register(self, name: str, plugin_class: Type[Plugin], 
                 manifest: PluginManifest) -> None:
        """Register a plugin class and manifest.
        
        Args:
            name: Plugin name
            plugin_class: Plugin class (subclass of Plugin)
            manifest: PluginManifest with plugin metadata
        """
        self._plugin_classes[name] = plugin_class
        self._manifests[name] = manifest
        logger.debug(f"Registered plugin: {name}")
    
    def get_plugin_class(self, name: str) -> Optional[Type[Plugin]]:
        """Get plugin class by name.
        
        Args:
            name: Plugin name
            
        Returns:
            Plugin class or None if not found
        """
        return self._plugin_classes.get(name)
    
    def get_manifest(self, name: str) -> Optional[PluginManifest]:
        """Get plugin manifest by name.
        
        Args:
            name: Plugin name
            
        Returns:
            PluginManifest or None if not found
        """
        return self._manifests.get(name)
    
    def list_plugins(self) -> Dict[str, PluginManifest]:
        """List all registered plugins.
        
        Returns:
            Dictionary mapping plugin names to manifests
        """
        return self._manifests.copy()
    
    def is_registered(self, name: str) -> bool:
        """Check if plugin is registered.
        
        Args:
            name: Plugin name
            
        Returns:
            True if registered
        """
        return name in self._plugin_classes
    
    def clear(self) -> None:
        """Clear all registered plugins.
        
        Useful for testing.
        """
        self._plugin_classes.clear()
        self._manifests.clear()
        logger.debug("Plugin registry cleared")
