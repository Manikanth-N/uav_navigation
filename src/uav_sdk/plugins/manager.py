"""
Plugin manager for lifecycle management and dependency resolution.

Handles plugin instantiation, initialization, startup, and shutdown in
correct dependency order.
"""

import asyncio
from typing import Dict, List, Optional
from collections import defaultdict
import logging

from .base import Plugin, PluginState
from .registry import PluginRegistry

logger = logging.getLogger(__name__)


class PluginManager:
    """Manages plugin lifecycle and dependency resolution.
    
    Responsible for:
    - Instantiating plugins in dependency order
    - Initializing plugins
    - Starting/stopping plugins
    - Detecting circular dependencies
    """
    
    def __init__(self, registry: PluginRegistry, runtime):
        """Initialize plugin manager.
        
        Args:
            registry: PluginRegistry with loaded plugin classes
            runtime: SDK runtime instance
        """
        self.registry = registry
        self.runtime = runtime
        self._instances: Dict[str, Plugin] = {}
        self._load_order: List[str] = []
    
    async def instantiate_plugins(self, config: Dict[str, Dict], 
                                  plugin_names: Optional[List[str]] = None
                                  ) -> bool:
        """Create plugin instances in dependency order.
        
        Resolves dependencies and instantiates plugins in correct order.
        
        Args:
            config: {plugin_name: plugin_config} dictionary
            plugin_names: Specific plugins to load (None = all registered)
            
        Returns:
            True if successful
        """
        # Resolve load order
        load_order = self._resolve_dependencies(plugin_names)
        if load_order is None:
            logger.error("Circular dependency detected in plugins")
            return False
        
        self._load_order = load_order
        logger.info(f"Plugin load order: {load_order}")
        
        # Instantiate in dependency order
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
        """Initialize all plugins in dependency order.
        
        Calls initialize() on each plugin in load order.
        
        Returns:
            True if all successful
        """
        logger.info("Initializing plugins...")
        
        for plugin_name in self._load_order:
            if plugin_name not in self._instances:
                logger.error(f"Plugin instance not found: {plugin_name}")
                return False
            
            plugin = self._instances[plugin_name]
            
            try:
                success = await plugin.initialize()
                if success:
                    plugin.state = PluginState.INITIALIZED
                    logger.info(f"Initialized plugin: {plugin_name}")
                else:
                    logger.error(f"Plugin initialization failed: {plugin_name}")
                    return False
            except Exception as e:
                logger.error(f"Error initializing {plugin_name}: {e}", exc_info=True)
                plugin.state = PluginState.ERROR
                return False
        
        logger.info("All plugins initialized successfully")
        return True
    
    async def start_plugins(self) -> bool:
        """Start all plugins in dependency order.
        
        Calls start() on each plugin in load order.
        
        Returns:
            True if all successful
        """
        logger.info("Starting plugins...")
        
        for plugin_name in self._load_order:
            plugin = self._instances[plugin_name]
            
            try:
                success = await plugin.start()
                if success:
                    plugin.state = PluginState.STARTED
                    logger.info(f"Started plugin: {plugin_name}")
                else:
                    logger.error(f"Plugin start failed: {plugin_name}")
                    # Continue with other plugins
            except Exception as e:
                logger.error(f"Error starting {plugin_name}: {e}", exc_info=True)
                plugin.state = PluginState.ERROR
        
        logger.info("Plugin startup complete")
        return True
    
    async def shutdown_plugins(self) -> bool:
        """Shutdown all plugins in reverse dependency order.
        
        Calls shutdown() on each plugin in reverse load order.
        
        Returns:
            True if all successful
        """
        logger.info("Shutting down plugins...")
        
        errors = []
        
        # Reverse order for cleanup
        for plugin_name in reversed(self._load_order):
            if plugin_name not in self._instances:
                continue
            
            plugin = self._instances[plugin_name]
            
            try:
                success = await plugin.shutdown()
                if success:
                    plugin.state = PluginState.STOPPED
                    logger.info(f"Shutdown plugin: {plugin_name}")
                else:
                    logger.error(f"Plugin shutdown failed: {plugin_name}")
                    errors.append(plugin_name)
            except Exception as e:
                logger.error(f"Error shutting down {plugin_name}: {e}")
                errors.append(plugin_name)
        
        if errors:
            logger.warning(f"Errors during shutdown: {errors}")
        else:
            logger.info("All plugins shut down successfully")
        
        return len(errors) == 0
    
    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get plugin instance by name.
        
        Args:
            name: Plugin name
            
        Returns:
            Plugin instance or None
        """
        return self._instances.get(name)
    
    def list_loaded_plugins(self) -> Dict[str, Plugin]:
        """List all loaded plugin instances.
        
        Returns:
            Dictionary mapping names to plugin instances
        """
        return self._instances.copy()
    
    def _resolve_dependencies(self, plugin_names: Optional[List[str]] = None
                             ) -> Optional[List[str]]:
        """Topologically sort plugins by dependencies (Kahn's algorithm).
        
        Args:
            plugin_names: Specific plugins to load (None = all registered)
            
        Returns:
            Sorted list of plugin names, or None if circular dependency
        """
        
        if plugin_names is None:
            plugin_names = list(self.registry.list_plugins().keys())
        
        # Build dependency graph
        graph = defaultdict(list)  # plugin -> list of plugins that depend on it
        in_degree = defaultdict(int)  # incoming edge count
        
        for name in plugin_names:
            if name not in in_degree:
                in_degree[name] = 0
            
            manifest = self.registry.get_manifest(name)
            if not manifest:
                logger.warning(f"Manifest not found: {name}")
                continue
            
            # Check each dependency
            for dep_name in manifest.dependencies:
                if dep_name in plugin_names:
                    # dep_name must come before name
                    graph[dep_name].append(name)
                    in_degree[name] += 1
                else:
                    # Dependency not in load set - that's okay, warn
                    logger.debug(f"Plugin {name} depends on {dep_name} which is not loaded")
        
        # Kahn's algorithm for topological sort
        queue = [n for n in plugin_names if in_degree[n] == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            # For each plugin that depends on this one
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # Check for cycles
        if len(result) != len(plugin_names):
            missing = set(plugin_names) - set(result)
            logger.error(f"Circular dependency detected in: {missing}")
            return None
        
        return result
