"""
Depth sensor plugin for UAV perception.

Provides depth sensing and 3D reconstruction capabilities.
"""

from typing import Any, Dict, List, Optional, Tuple
import asyncio
import cv2
import numpy as np
import logging
from dataclasses import dataclass

from uav_sdk.plugins.base import DriverPlugin, PluginInfo, PluginState

logger = logging.getLogger(__name__)


@dataclass
class DepthReading:
    """Depth sensor reading."""
    depth_map: np.ndarray
    timestamp: float
    min_depth: float
    max_depth: float
    valid_pixels: int


class DepthSensorPlugin(DriverPlugin):
    """Depth sensor driver plugin."""

    def __init__(self, config: Dict[str, Any], runtime):
        super().__init__(config, runtime)
        self.depth_stream = None
        self.is_streaming = False
        self._stream_task = None
        self.last_reading: Optional[DepthReading] = None

    def get_info(self):
        return PluginInfo(
            name="depth_sensor",
            version="0.1.0",
            author="SDK Team",
            description="Depth sensing and 3D reconstruction",
            plugin_type="perception",
            dependencies=[],
            features=["depth_sensing", "3d_reconstruction", "obstacle_detection"],
            config_schema={
                "sensor_type": {"type": "string", "enum": ["stereo", "lidar", "tof"], "default": "stereo"},
                "max_range": {"type": "number", "default": 10.0},  # meters
                "min_range": {"type": "number", "default": 0.1},   # meters
                "resolution": {"type": "string", "default": "640x480"},
                "stream_enabled": {"type": "boolean", "default": False},
                "stream_interval": {"type": "number", "default": 0.1},
            },
        )

    async def initialize(self) -> bool:
        try:
            sensor_type = self.config.get("sensor_type", "stereo")

            if sensor_type == "stereo":
                # Initialize stereo camera setup
                success = await self._init_stereo_camera()
            elif sensor_type == "lidar":
                # Initialize LIDAR sensor
                success = await self._init_lidar()
            elif sensor_type == "tof":
                # Initialize Time-of-Flight sensor
                success = await self._init_tof()
            else:
                logger.error(f"Unknown sensor type: {sensor_type}")
                return False

            if not success:
                return False

            logger.info(f"Depth sensor initialized: {sensor_type}")
            self.state = PluginState.INITIALIZED
            return True

        except Exception as e:
            logger.error(f"Depth sensor initialization failed: {e}")
            return False

    async def start(self) -> bool:
        if self.config.get("stream_enabled", False):
            self._stream_task = asyncio.create_task(self._stream_depth())
            logger.info("Depth streaming started")

        self.state = PluginState.STARTED
        return True

    async def shutdown(self) -> bool:
        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass

        # Cleanup sensor resources
        if self.depth_stream:
            # Close sensor connections
            pass

        self.state = PluginState.STOPPED
        logger.info("Depth sensor shutdown")
        return True

    async def read_sensor(self, sensor_id: str) -> Any:
        """Read depth data from sensor.

        Args:
            sensor_id: "depth" for depth map, "pointcloud" for 3D points

        Returns:
            DepthReading or point cloud data
        """
        if sensor_id == "depth":
            return await self._read_depth_map()
        elif sensor_id == "pointcloud":
            return await self._read_pointcloud()
        else:
            return None

    async def write_actuator(self, actuator_id: str, value: Any) -> bool:
        """Control depth sensor settings.

        Args:
            actuator_id: Setting to control
            value: New value

        Returns:
            True if successful
        """
        try:
            if actuator_id == "max_range":
                self.config["max_range"] = value
            elif actuator_id == "min_range":
                self.config["min_range"] = value
            else:
                logger.warning(f"Unknown depth sensor control: {actuator_id}")
                return False

            logger.debug(f"Set {actuator_id} to {value}")
            return True

        except Exception as e:
            logger.error(f"Failed to set {actuator_id}: {e}")
            return False

    async def _init_stereo_camera(self) -> bool:
        """Initialize stereo camera for depth sensing."""
        # In a real implementation, this would set up stereo camera pair
        # For simulation, we'll create a mock depth sensor
        logger.info("Initializing stereo camera depth sensor (simulated)")
        return True

    async def _init_lidar(self) -> bool:
        """Initialize LIDAR sensor."""
        # In a real implementation, this would connect to LIDAR hardware
        logger.info("Initializing LIDAR sensor (simulated)")
        return True

    async def _init_tof(self) -> bool:
        """Initialize Time-of-Flight sensor."""
        # In a real implementation, this would connect to ToF sensor
        logger.info("Initializing ToF sensor (simulated)")
        return True

    async def _read_depth_map(self) -> Optional[DepthReading]:
        """Read depth map from sensor."""
        try:
            # Parse resolution
            resolution = self.config.get("resolution", "640x480")
            width, height = map(int, resolution.split('x'))

            # Generate simulated depth map
            # In real implementation, this would read from actual sensor
            depth_map = self._generate_simulated_depth(width, height)

            # Calculate statistics
            valid_mask = depth_map > 0
            min_depth = float(np.min(depth_map[valid_mask])) if np.any(valid_mask) else 0.0
            max_depth = float(np.max(depth_map[valid_mask])) if np.any(valid_mask) else 0.0
            valid_pixels = int(np.sum(valid_mask))

            reading = DepthReading(
                depth_map=depth_map,
                timestamp=asyncio.get_event_loop().time(),
                min_depth=min_depth,
                max_depth=max_depth,
                valid_pixels=valid_pixels
            )

            self.last_reading = reading
            return reading

        except Exception as e:
            logger.error(f"Failed to read depth map: {e}")
            return None

    async def _read_pointcloud(self) -> Optional[np.ndarray]:
        """Read 3D point cloud from sensor."""
        depth_reading = await self._read_depth_map()
        if depth_reading is None:
            return None

        # Convert depth map to point cloud
        # This is a simplified conversion - real implementation would use camera intrinsics
        height, width = depth_reading.depth_map.shape
        points = []

        for v in range(height):
            for u in range(width):
                depth = depth_reading.depth_map[v, u]
                if depth > 0:
                    # Simple pinhole camera model (simplified)
                    x = (u - width/2) * depth / 500.0  # focal length approximation
                    y = (v - height/2) * depth / 500.0
                    z = depth
                    points.append([x, y, z])

        return np.array(points) if points else None

    def _generate_simulated_depth(self, width: int, height: int) -> np.ndarray:
        """Generate simulated depth map for testing."""
        # Create a simple simulated depth scene
        depth_map = np.full((height, width), 5.0, dtype=np.float32)  # 5m background

        # Add some obstacles
        center_x, center_y = width // 2, height // 2

        # Create a wall-like obstacle
        cv2.rectangle(depth_map, (center_x - 50, center_y - 100),
                     (center_x + 50, center_y + 100), 2.0, -1)

        # Add some noise
        noise = np.random.normal(0, 0.1, (height, width))
        depth_map += noise
        depth_map = np.clip(depth_map, 0.1, 10.0)  # Clamp to valid range

        return depth_map

    async def _stream_depth(self):
        """Continuously stream depth data as events."""
        interval = self.config.get("stream_interval", 0.1)

        try:
            while self.is_streaming and self.state == PluginState.STARTED:
                depth_reading = await self._read_depth_map()
                if depth_reading is not None:
                    # Publish depth event
                    await self.runtime.event_system.publish("depth.reading", reading=depth_reading)

                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            logger.info("Depth streaming cancelled")
        except Exception as e:
            logger.error(f"Depth streaming error: {e}")

    def detect_obstacles(self, depth_map: np.ndarray, threshold: float = 2.0) -> List[Tuple]:
        """Detect obstacles in depth map.

        Args:
            depth_map: Depth map array
            threshold: Distance threshold for obstacle detection

        Returns:
            List of obstacle bounding boxes (x, y, w, h, min_depth)
        """
        obstacles = []

        # Simple obstacle detection - find regions closer than threshold
        obstacle_mask = (depth_map > 0) & (depth_map < threshold)

        # Find contours of obstacles
        contours, _ = cv2.findContours(obstacle_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            if cv2.contourArea(contour) > 100:  # Minimum area threshold
                x, y, w, h = cv2.boundingRect(contour)
                region_depths = depth_map[y:y+h, x:x+w]
                valid_depths = region_depths[region_depths > 0]
                min_depth = float(np.min(valid_depths)) if len(valid_depths) > 0 else 0.0

                obstacles.append((x, y, w, h, min_depth))

        return obstacles

    def get_sensor_info(self) -> Dict:
        """Get depth sensor information."""
        return {
            "sensor_type": self.config.get("sensor_type", "stereo"),
            "max_range": self.config.get("max_range", 10.0),
            "min_range": self.config.get("min_range", 0.1),
            "resolution": self.config.get("resolution", "640x480"),
            "streaming": self.is_streaming,
            "last_reading": self.last_reading is not None,
        }