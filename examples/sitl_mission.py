#!/usr/bin/env python3
"""
SITL Mission Example

Demonstrates full mission execution with MAVLink SITL integration.
Loads mission planner and autopilot plugins, connects to SITL, and executes a waypoint mission.
"""

import asyncio
import logging
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from uav_sdk.core.sdk import UAVDriver
from uav_sdk.plugins import MissionPlannerPlugin, AutopilotPlugin, MavlinkProtocolPlugin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main mission execution example."""

    # Create SDK instance
    sdk = UAVDriver()

    # Define mission waypoints (around a typical test field)
    mission_waypoints = [
        {"lat": 37.7749, "lon": -122.4194, "alt": 20.0, "speed": 5.0, "hold_time": 2.0},  # SF
        {"lat": 37.7849, "lon": -122.4094, "alt": 25.0, "speed": 5.0, "hold_time": 1.0},  # North
        {"lat": 37.7649, "lon": -122.4294, "alt": 20.0, "speed": 5.0, "hold_time": 1.0},  # South
        {"lat": 37.7749, "lon": -122.4194, "alt": 15.0, "speed": 5.0, "hold_time": 0.0},  # Back to start
    ]

    # Create plugin instances manually for this example
    mavlink_config = {"connection": "tcp://127.0.0.1:5763", "auto_connect": True}
    mission_config = {"default_speed": 5.0, "reached_threshold": 2.0}
    autopilot_config = {"takeoff_altitude": 10.0, "cruise_speed": 5.0, "auto_arm": False}

    mavlink_plugin = MavlinkProtocolPlugin(mavlink_config, sdk)
    mission_plugin = MissionPlannerPlugin(mission_config, sdk)
    autopilot_plugin = AutopilotPlugin(autopilot_config, sdk)

    try:
        # Initialize plugins
        logger.info("Initializing plugins...")
        await mavlink_plugin.initialize()
        await mission_plugin.initialize()
        await autopilot_plugin.initialize()

        # Start plugins
        logger.info("Starting plugins...")
        await mavlink_plugin.start()
        await mission_plugin.start()
        await autopilot_plugin.start()

        # Wait for connection
        logger.info("Waiting for SITL connection...")
        await asyncio.sleep(3.0)

        # Load mission
        logger.info("Loading mission...")
        mission_result = await mission_plugin.process({"command": "load_mission", "waypoints": mission_waypoints})
        logger.info(f"Mission load result: {mission_result}")

        # Get mission status
        status = await mission_plugin.process({"command": "get_status"})
        logger.info(f"Mission status: {status}")

        # Manual arm (for safety)
        logger.info("Arming vehicle...")
        arm_result = await autopilot_plugin.process({"command": "arm"})
        logger.info(f"Arm result: {arm_result}")

        # Wait for arming
        await asyncio.sleep(2.0)

        # Start mission
        logger.info("Starting mission...")
        start_result = await mission_plugin.process({"command": "start_mission"})
        logger.info(f"Mission start result: {start_result}")

        # Monitor mission progress
        logger.info("Monitoring mission progress...")
        mission_complete = False

        while not mission_complete:
            await asyncio.sleep(2.0)

            # Get current status
            status = await mission_plugin.process({"command": "get_status"})
            autopilot_status = await autopilot_plugin.process({"command": "get_status"})

            logger.info(f"Mission: {status}")
            logger.info(f"Vehicle: {autopilot_status}")

            # Check if mission completed
            if not status.get("active", False) and status.get("current_waypoint", -1) >= len(mission_waypoints) - 1:
                mission_complete = True
                logger.info("Mission completed!")

        # Land the vehicle
        logger.info("Landing vehicle...")
        land_result = await autopilot_plugin.process({"command": "land"})
        logger.info(f"Land result: {land_result}")

        # Wait for landing
        await asyncio.sleep(5.0)

        # Disarm
        logger.info("Disarming vehicle...")
        disarm_result = await autopilot_plugin.process({"command": "disarm"})
        logger.info(f"Disarm result: {disarm_result}")

    except KeyboardInterrupt:
        logger.info("Interrupted by user")

    except Exception as e:
        logger.error(f"Mission failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        logger.info("Shutting down...")
        await autopilot_plugin.shutdown()
        await mission_plugin.shutdown()
        await mavlink_plugin.shutdown()
        logger.info("Done!")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())