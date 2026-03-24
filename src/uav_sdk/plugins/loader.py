"""
Plugin loader for discovering and dynamically loading plugins.

Supports automatic discovery in plugin directories and dynamic imports.
"""

import importlib
import sys
from pathlib import Path
from typing import Dict, Optional, Type, List
import logging

from .manifest import ManifestLoader, PluginManifest
from .base import Plugin
from .registry import PluginRegistry

logger = logging.getLogger(__name__)


class PluginLoader:
    """Discovers and loads plugins from filesystem.
    
    Scans plugin directories for plugin.yaml files and dynamically
    imports plugin classes.
    """
    
    def __init__(self, plugin_dirs: Optional[List[str]] = None):
        """Initialize plugin loader.
        
        Args:
            plugin_dirs: List of directories to search for plugins
        """
        self.plugin_dirs = [Path(d).resolve() for d in (plugin_dirs or [])]
        self.registry = PluginRegistry()
        self._discovered: Dict[str, PluginManifest] = {}
    
    def add_plugin_dir(self, plugin_dir: str) -> None:
        """Add a plugin directory to search path.
        
        Args:
            plugin_dir: Path to plugin directory
        """
        path = Path(plugin_dir).resolve()
        if path not in self.plugin_dirs:
            self.plugin_dirs.append(path)
            logger.debug(f"Added plugin search directory: {path}")
    
    def discover(self) -> Dict[str, PluginManifest]:
        """Discover all available plugins.
        
        Scans plugin directories for plugin.yaml/plugin.json files.
        
        Returns:
            Dictionary mapping plugin names to manifests
        """
        discovered = {}
        
        for plugin_dir in self.plugin_dirs:
            if not plugin_dir.exists():
                logger.warning(f"Plugin directory not found: {plugin_dir}")
                continue
            
            # Look for plugin.yaml or plugin.json in subdirectories
            for manifest_file in plugin_dir.glob('*/plugin.yaml'):
                try:
                    manifest = ManifestLoader.load(manifest_file)
                    discovered[manifest.name] = manifest
                    logger.info(
                        f"Discovered plugin: {manifest.name} v{manifest.version} "
                        f"({manifest_file.parent.name})"
                    )
                except Exception as e:
                    logger.error(f"Failed to load manifest {manifest_file}: {e}")
            
            # Also try .json manifests
            for manifest_file in plugin_dir.glob('*/plugin.json'):
                try:
                    manifest = ManifestLoader.load(manifest_file)
                    if manifest.name not in discovered:
                        discovered[manifest.name] = manifest
                        logger.info(f"Discovered plugin: {manifest.name}")
                except Exception as e:
                    logger.error(f"Failed to load manifest {manifest_file}: {e}")
        
        self._discovered = discovered
        return discovered
    
    def load_plugin(self, name: str, manifest: PluginManifest) -> bool:
        """Load a specific plugin class.
        
        Dynamically imports the plugin class and registers it.
        
        Args:
            name: Plugin name
            manifest: PluginManifest
            
        Returns:
            True if successful
        """
        try:
            # Parse entry point (format: "module.path:ClassName")
            if ':' not in manifest.entry_point:
                logger.error(
                    f"Invalid entry_point for {name}: {manifest.entry_point}"
                )
                return False
            
            module_path, class_name = manifest.entry_point.split(':')
            
            logger.debug(f"Importing {module_path}:{class_name}")
            
            # Dynamically import module
            try:
                module = importlib.import_module(module_path)
            except ModuleNotFoundError as e:
                logger.error(
                    f"Failed to import module {module_path} for plugin {name}: {e}"
                )
                return False
            
            # Get class from module
            try:
                plugin_class = getattr(module, class_name)
            except AttributeError:
                logger.error(
                    f"Class {class_name} not found in module {module_path}"
                )
                return False
            
            # Validate it's a Plugin subclass
            if not issubclass(plugin_class, Plugin):
                logger.error(
                    f"Plugin class {class_name} is not a Plugin subclass"
                )
                return False
            
            # Register in registry
            self.registry.register(name, plugin_class, manifest)
            logger.info(f"Loaded plugin: {name} ({manifest.description})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load plugin {name}: {e}")
            return False
    
    def load_all(self, selected_plugins: Optional[List[str]] = None) -> bool:
        """Load all or selected plugins.
        
        Args:
            selected_plugins: List of plugin names to load.
                            If None, loads all discovered plugins.
            
        Returns:
            True if all requested plugins loaded successfully
        """
        # Discover if not already done
        if not self._discovered:
            self.discover()
        
        # Determine which plugins to load
        if selected_plugins:
            to_load = {
                name: self._discovered[name]
                for name in selected_plugins
                if name in self._discovered
            }
            missing = set(selected_plugins) - set(to_load.keys())
            if missing:
                logger.warning(f"Requested plugins not discovered: {missing}")
        else:
            to_load = self._discovered
        
        # Load each plugin
        success_count = 0
        for name, manifest in to_load.items():
            if self.load_plugin(name, manifest):
                success_count += 1
        
        logger.info(
            f"Loaded {success_count}/{len(to_load)} plugins successfully"
        )
        
        return success_count == len(to_load)
    
    def get_registry(self) -> PluginRegistry:
        """Get the plugin registry.
        
        Returns:
            PluginRegistry instance
        """
        return self.registry
