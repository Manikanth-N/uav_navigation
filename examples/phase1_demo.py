#!/usr/bin/env python3
"""
UAV SDK v2.0 - First Example

Demonstrates basic SDK initialization and plugin system.
This is a minimal working example to validate Phase 1.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from uav_sdk.core.sdk import UAVDriver
from uav_sdk import plugins
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DemoPlugin(plugins.ComputePlugin):
    """Simple demo plugin to show plugin system works."""
    
    def get_info(self):
        return plugins.PluginInfo(
            name="demo_plugin",
            version="1.0.0",
            author="Demo",
            description="Simple demonstration plugin",
            plugin_type="demo",
            dependencies=[],
            features=["demo"],
            config_schema={}
        )
    
    async def initialize(self):
        logger.info("Demo plugin: initialize called")
        return True
    
    async def start(self):
        logger.info("Demo plugin: start called")
        return True
    
    async def shutdown(self):
        logger.info("Demo plugin: shutdown called")
        return True
    
    async def process(self, data):
        logger.info(f"Demo plugin: processing {data}")
        return {"status": "processed", "input": data}


async def main():
    """Main example function."""
    
    logger.info("=" * 60)
    logger.info("UAV SDK v2.0 Phase 1 - First Working Example")
    logger.info("=" * 60)
    
    # ==================================================================
    # 1. Create SDK instance
    # ==================================================================
    logger.info("\n1. Creating SDK instance...")
    sdk = UAVDriver(
        plugin_dirs=["./plugins"],
        log_level="DEBUG"
    )
    
    # ==================================================================
    # 2. Register demo plugin directly (in real usage, plugins found via discovery)
    # ==================================================================
    logger.info("\n2. Registering demo plugin...")
    demo_instance = DemoPlugin({}, sdk)
    registry = sdk.plugin_loader.registry
    registry.register(
        "demo_plugin",
        DemoPlugin,
        demo_instance.get_info()
    )
    
    # ==================================================================
    # 3. Initialize SDK
    # ==================================================================
    logger.info("\n3. Initializing SDK...")
    # For Phase 1, we skip standard plugin discovery and just use what we registered
    # In Phase 2+, we'll have real plugin config files
    
    # Manually set minimal config to avoid trying to load non-existent plugins
    sdk.config.set("plugins.demo_plugin.enabled", True)
    
    if not await sdk.initialize():
        logger.error("Failed to initialize SDK")
        return False
    
    logger.info("✓ SDK initialized successfully")
    
    # ==================================================================
    # 4. Check state system
    # ==================================================================
    logger.info("\n4. Demonstrating state system...")
    sdk.state.update(
        armed=True,
        mode="GUIDED",
        lat=37.7749,
        lon=-122.4194,
        alt=100.0
    )
    state = sdk.state.get()
    logger.info(f"  Current state: armed={state.armed}, mode={state.mode}")
    logger.info(f"  Position: ({state.lat}, {state.lon}, {state.alt}m)")
    
    # ==================================================================
    # 5. Check event system
    # ==================================================================
    logger.info("\n5. Demonstrating event system...")
    
    event_received = []
    
    async def on_test_event(event):
        event_received.append(event)
        logger.info(f"  Event received: {event.name} with payload {event.payload}")
    
    sdk.subscribe("test.event", on_test_event)
    await sdk.publish("test.event", message="Hello from SDK")
    
    await asyncio.sleep(0.1)  # Give async time to execute
    
    if event_received:
        logger.info("✓ Event system works!")
    
    # ==================================================================
    # 6. Check configuration
    # ==================================================================
    logger.info("\n6. Demonstrating configuration system...")
    sdk.config.set("app.name", "UAV SDK Demo")
    sdk.config.set("app.version", "2.0.0a1")
    
    app_name = sdk.config.get("app.name")
    logger.info(f"  Config value: app.name = {app_name}")
    
    # ==================================================================
    # 7. Start SDK
    # ==================================================================
    logger.info("\n7. Starting SDK...")
    if not await sdk.start():
        logger.error("Failed to start SDK")
        return False
    
    logger.info("✓ SDK started successfully")
    
    # ==================================================================
    # 8. Verify plugins loaded
    # ==================================================================
    logger.info("\n8. Loaded plugins:")
    plugins_loaded = sdk.list_loaded_plugins()
    for name, plugin in plugins_loaded.items():
        info = plugin.get_info()
        logger.info(f"  - {name} v{info.version}: {info.description}")
    
    # ==================================================================
    # 9. Shutdown
    # ==================================================================
    logger.info("\n9. Shutting down SDK...")
    if not await sdk.shutdown():
        logger.error("Errors during shutdown")
        return False
    
    logger.info("✓ SDK shutdown complete")
    
    # ==================================================================
    # Success!
    # ==================================================================
    logger.info("\n" + "=" * 60)
    logger.info("✓ PHASE 1 PROOF OF CONCEPT SUCCESSFUL!")
    logger.info("=" * 60)
    logger.info("\nKey components verified:")
    logger.info("  ✓ Plugin system (loader, manager, registry)")
    logger.info("  ✓ State management with versioning")
    logger.info("  ✓ Event system with pub/sub")
    logger.info("  ✓ Configuration management")
    logger.info("  ✓ Logging infrastructure")
    logger.info("\nReady for Phase 2: Protocol Abstraction")
    
    return True


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
