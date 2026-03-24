#!/usr/bin/env python3
"""
Perception Pipeline Example

Demonstrates computer vision and sensor fusion capabilities.
Shows camera capture, object detection, depth sensing, and sensor fusion.
"""

import asyncio
import cv2
import numpy as np
import logging
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from uav_sdk.core.sdk import UAVDriver
from uav_sdk.plugins import CameraPlugin, ObjectDetectionPlugin, DepthSensorPlugin, SensorFusionPlugin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main perception pipeline example."""

    # Create SDK instance
    sdk = UAVDriver()

    # Plugin configurations
    camera_config = {
        "camera": {
            "device_id": 0,
            "width": 640,
            "height": 480,
            "fps": 15,
            "auto_exposure": True,
        },
        "stream_enabled": True,
        "stream_interval": 0.2,
    }

    detection_config = {
        "model": {
            "config_path": "models/yolov3.cfg",
            "weights_path": "models/yolov3.weights",
            "classes_path": "models/coco.names",
        },
        "confidence_threshold": 0.3,
        "input_size": 320,
        "process_interval": 0.2,
    }

    depth_config = {
        "sensor_type": "stereo",
        "max_range": 10.0,
        "min_range": 0.1,
        "resolution": "320x240",
        "stream_enabled": True,
        "stream_interval": 0.2,
    }

    fusion_config = {
        "fusion_method": "weighted_average",
        "fusion_rate": 5.0,
        "position_weight": 0.7,
        "orientation_weight": 0.8,
    }

    try:
        # Create plugin instances
        camera_plugin = CameraPlugin(camera_config, sdk)
        detection_plugin = ObjectDetectionPlugin(detection_config, sdk)
        depth_plugin = DepthSensorPlugin(depth_config, sdk)
        fusion_plugin = SensorFusionPlugin(fusion_config, sdk)

        # Initialize plugins
        logger.info("Initializing perception plugins...")
        await camera_plugin.initialize()
        await detection_plugin.initialize()
        await depth_plugin.initialize()
        await fusion_plugin.initialize()

        # Start plugins
        logger.info("Starting perception pipeline...")
        await camera_plugin.start()
        await detection_plugin.start()
        await depth_plugin.start()
        await fusion_plugin.start()

        # Set up event handlers for demonstration
        detection_count = 0
        depth_readings = 0
        fusion_updates = 0

        def on_detections(event):
            nonlocal detection_count
            detection_count += 1
            detections = event.get('detections', [])
            logger.info(f"Detections: {len(detections)} objects found")

        def on_depth_reading(event):
            nonlocal depth_readings
            depth_readings += 1
            reading = event.get('reading')
            if reading:
                logger.info(".2f")

        def on_fused_state(event):
            nonlocal fusion_updates
            fusion_updates += 1
            state = event.get('state')
            if state:
                pos = state.position
                conf = state.confidence
                sensors = len(state.sensors_used)
                logger.info(".2f")

        # Subscribe to events
        sdk.subscribe("detection.objects", on_detections)
        sdk.subscribe("depth.reading", on_depth_reading)
        sdk.subscribe("fusion.state", on_fused_state)

        # Run perception pipeline for 10 seconds
        logger.info("Running perception pipeline for 10 seconds...")
        await asyncio.sleep(10)

        # Get final statistics
        camera_info = camera_plugin.get_camera_info()
        detection_stats = detection_plugin.get_detection_stats()
        depth_info = depth_plugin.get_sensor_info()
        fused_state = fusion_plugin._get_fused_state()

        logger.info("=== Perception Pipeline Results ===")
        logger.info(f"Camera: {camera_info}")
        logger.info(f"Detection: {detection_stats}")
        logger.info(f"Depth Sensor: {depth_info}")
        logger.info(f"Fused State: {fused_state}")
        logger.info(f"Event Counts: detections={detection_count}, depth={depth_readings}, fusion={fusion_updates}")

        # Demonstrate manual processing
        logger.info("=== Manual Processing Demo ===")

        # Capture image manually
        image = await camera_plugin.read_sensor("image")
        if image is not None:
            logger.info(f"Manual image capture: {image.shape}")

            # Run detection on captured image
            detections = await detection_plugin.process(image)
            logger.info(f"Manual detection: {len(detections.get('detections', []))} objects")

        # Get depth reading manually
        depth_reading = await depth_plugin.read_sensor("depth")
        if depth_reading:
            logger.info(".2f")

            # Detect obstacles
            obstacles = depth_plugin.detect_obstacles(depth_reading.depth_map, threshold=3.0)
            logger.info(f"Obstacle detection: {len(obstacles)} obstacles found")

        # Get point cloud
        pointcloud = await depth_plugin.read_sensor("pointcloud")
        if pointcloud is not None:
            logger.info(f"Point cloud: {len(pointcloud)} points")

    except KeyboardInterrupt:
        logger.info("Interrupted by user")

    except Exception as e:
        logger.error(f"Perception pipeline failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        logger.info("Shutting down perception pipeline...")
        await fusion_plugin.shutdown()
        await depth_plugin.shutdown()
        await detection_plugin.shutdown()
        await camera_plugin.shutdown()
        logger.info("Done!")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())