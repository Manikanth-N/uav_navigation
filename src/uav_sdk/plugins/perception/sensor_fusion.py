"""
Sensor fusion plugin for UAV perception.

Combines data from multiple sensors for robust state estimation.
"""

from typing import Any, Dict, List, Optional, Tuple
import asyncio
import numpy as np
import logging
from dataclasses import dataclass, field
from collections import deque

from uav_sdk.plugins.base import ComputePlugin, PluginInfo, PluginState

logger = logging.getLogger(__name__)


@dataclass
class FusedState:
    """Fused sensor state estimate."""
    timestamp: float
    position: Tuple[float, float, float]  # x, y, z
    velocity: Tuple[float, float, float]  # vx, vy, vz
    orientation: Tuple[float, float, float, float]  # quaternion: w, x, y, z
    confidence: float  # Overall confidence in estimate
    sensors_used: List[str] = field(default_factory=list)


@dataclass
class SensorMeasurement:
    """Individual sensor measurement."""
    sensor_type: str
    timestamp: float
    data: Any
    covariance: Optional[np.ndarray] = None
    confidence: float = 1.0


class SensorFusionPlugin(ComputePlugin):
    """Sensor fusion plugin combining multiple sensor inputs."""

    def __init__(self, config: Dict[str, Any], runtime):
        super().__init__(config, runtime)
        self.measurement_buffer: deque = deque(maxlen=100)
        self.fused_state: Optional[FusedState] = None
        self._fusion_task = None

    def get_info(self):
        return PluginInfo(
            name="sensor_fusion",
            version="0.1.0",
            author="SDK Team",
            description="Multi-sensor fusion for robust state estimation",
            plugin_type="perception",
            dependencies=["camera", "depth_sensor"],  # Can work with any sensors
            features=["state_estimation", "sensor_fusion", "kalman_filtering"],
            config_schema={
                "fusion_method": {"type": "string", "enum": ["kalman", "complementary", "weighted_average"], "default": "weighted_average"},
                "buffer_size": {"type": "integer", "default": 100},
                "fusion_rate": {"type": "number", "default": 10.0},  # Hz
                "max_age": {"type": "number", "default": 1.0},  # seconds
                "position_weight": {"type": "number", "default": 0.7},
                "velocity_weight": {"type": "number", "default": 0.6},
                "orientation_weight": {"type": "number", "default": 0.8},
            },
        )

    async def initialize(self) -> bool:
        # Subscribe to sensor events
        self.subscribe("camera.image", self._on_camera_measurement)
        self.subscribe("depth.reading", self._on_depth_measurement)
        self.subscribe("detection.objects", self._on_detection_measurement)
        self.subscribe("mavlink.GLOBAL_POSITION_INT", self._on_gps_measurement)
        self.subscribe("mavlink.ATTITUDE", self._on_imu_measurement)

        # Initialize fusion state
        self.fused_state = FusedState(
            timestamp=0.0,
            position=(0.0, 0.0, 0.0),
            velocity=(0.0, 0.0, 0.0),
            orientation=(1.0, 0.0, 0.0, 0.0),  # Identity quaternion
            confidence=0.0
        )

        logger.info("Sensor fusion initialized")
        self.state = PluginState.INITIALIZED
        return True

    async def start(self) -> bool:
        # Start fusion processing task
        fusion_interval = 1.0 / self.config.get("fusion_rate", 10.0)
        self._fusion_task = asyncio.create_task(self._fusion_loop(fusion_interval))

        logger.info("Sensor fusion started")
        self.state = PluginState.STARTED
        return True

    async def shutdown(self) -> bool:
        if self._fusion_task:
            self._fusion_task.cancel()
            try:
                await self._fusion_task
            except asyncio.CancelledError:
                pass

        self.state = PluginState.STOPPED
        logger.info("Sensor fusion shutdown")
        return True

    async def process(self, input_data: Any) -> Any:
        """Process sensor measurements for fusion.

        Args:
            input_data: Dict with sensor measurements or manual fusion request

        Returns:
            Current fused state
        """
        if isinstance(input_data, dict):
            command = input_data.get("command")
            if command == "get_state":
                return self._get_fused_state()
            elif command == "add_measurement":
                measurement = input_data.get("measurement")
                if measurement:
                    await self._add_measurement(measurement)
                return {"status": "measurement_added"}
            elif command == "fuse_now":
                await self._perform_fusion()
                return self._get_fused_state()

        return {"error": "Unknown command"}

    async def _fusion_loop(self, interval: float):
        """Main fusion processing loop."""
        try:
            while self.state == PluginState.STARTED:
                await self._perform_fusion()
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("Fusion loop cancelled")
        except Exception as e:
            logger.error(f"Fusion loop error: {e}")

    async def _perform_fusion(self):
        """Perform sensor fusion to update state estimate."""
        if not self.measurement_buffer:
            return

        # Remove old measurements
        current_time = asyncio.get_event_loop().time()
        max_age = self.config.get("max_age", 1.0)

        while self.measurement_buffer and (current_time - self.measurement_buffer[0].timestamp) > max_age:
            self.measurement_buffer.popleft()

        if not self.measurement_buffer:
            return

        # Group measurements by type
        measurements_by_type = {}
        for measurement in self.measurement_buffer:
            if measurement.sensor_type not in measurements_by_type:
                measurements_by_type[measurement.sensor_type] = []
            measurements_by_type[measurement.sensor_type].append(measurement)

        # Perform fusion based on method
        fusion_method = self.config.get("fusion_method", "weighted_average")

        if fusion_method == "weighted_average":
            await self._weighted_average_fusion(measurements_by_type)
        elif fusion_method == "complementary":
            await self._complementary_fusion(measurements_by_type)
        elif fusion_method == "kalman":
            await self._kalman_fusion(measurements_by_type)

        # Publish fused state
        await self.runtime.event_system.publish("fusion.state", state=self.fused_state)

    async def _weighted_average_fusion(self, measurements_by_type: Dict[str, List[SensorMeasurement]]):
        """Simple weighted average fusion."""
        position_estimates = []
        velocity_estimates = []
        orientation_estimates = []
        sensors_used = []

        # Collect estimates from different sensors
        for sensor_type, measurements in measurements_by_type.items():
            latest = measurements[-1]  # Use most recent

            if sensor_type == "gps":
                # GPS provides position
                if hasattr(latest.data, 'lat') and hasattr(latest.data, 'lon'):
                    lat = getattr(latest.data, 'lat', 0) / 1e7  # Convert from MAVLink format
                    lon = getattr(latest.data, 'lon', 0) / 1e7
                    alt = getattr(latest.data, 'alt', 0) / 1000.0
                    position_estimates.append((lat, lon, alt))
                    sensors_used.append("gps")

            elif sensor_type == "imu":
                # IMU provides orientation and possibly velocity
                if hasattr(latest.data, 'roll') and hasattr(latest.data, 'pitch') and hasattr(latest.data, 'yaw'):
                    roll = getattr(latest.data, 'roll', 0) / 100.0  # Convert from centidegrees
                    pitch = getattr(latest.data, 'pitch', 0) / 100.0
                    yaw = getattr(latest.data, 'yaw', 0) / 100.0
                    # Convert to quaternion (simplified)
                    cr = np.cos(roll * 0.5)
                    sr = np.sin(roll * 0.5)
                    cp = np.cos(pitch * 0.5)
                    sp = np.sin(pitch * 0.5)
                    cy = np.cos(yaw * 0.5)
                    sy = np.sin(yaw * 0.5)

                    w = cr * cp * cy + sr * sp * sy
                    x = sr * cp * cy - cr * sp * sy
                    y = cr * sp * cy + sr * cp * sy
                    z = cr * cp * sy - sr * sp * cy

                    orientation_estimates.append((w, x, y, z))
                    sensors_used.append("imu")

            elif sensor_type == "depth":
                # Depth sensor provides altitude/height
                if hasattr(latest.data, 'depth_map') and latest.data.depth_map is not None:
                    # Estimate height from depth map (simplified)
                    avg_depth = np.mean(latest.data.depth_map[latest.data.depth_map > 0])
                    if avg_depth > 0:
                        height = 1.0 / avg_depth  # Simplified inverse depth
                        position_estimates.append((0, 0, height))  # Relative height
                        sensors_used.append("depth")

        # Fuse estimates
        fused_position = self._weighted_fuse_positions(position_estimates, self.config.get("position_weight", 0.7))
        fused_orientation = self._weighted_fuse_orientations(orientation_estimates, self.config.get("orientation_weight", 0.8))

        # Update state
        confidence = min(1.0, len(sensors_used) / 3.0)  # Simple confidence based on sensor count

        self.fused_state = FusedState(
            timestamp=asyncio.get_event_loop().time(),
            position=fused_position,
            velocity=(0.0, 0.0, 0.0),  # Not fusing velocity yet
            orientation=fused_orientation,
            confidence=confidence,
            sensors_used=sensors_used
        )

    async def _complementary_fusion(self, measurements_by_type: Dict[str, List[SensorMeasurement]]):
        """Complementary filter fusion (simpler than Kalman)."""
        # Simplified complementary filter implementation
        # In practice, this would use low-pass/high-pass filtering
        await self._weighted_average_fusion(measurements_by_type)

    async def _kalman_fusion(self, measurements_by_type: Dict[str, List[SensorMeasurement]]):
        """Kalman filter fusion (advanced)."""
        # Full Kalman filter implementation would be complex
        # For now, fall back to weighted average
        logger.warning("Kalman fusion not fully implemented, using weighted average")
        await self._weighted_average_fusion(measurements_by_type)

    def _weighted_fuse_positions(self, positions: List[Tuple], weight: float) -> Tuple:
        """Fuse multiple position estimates."""
        if not positions:
            return (0.0, 0.0, 0.0)

        if len(positions) == 1:
            return positions[0]

        # Simple weighted average
        weights = [weight] * len(positions)
        weights[-1] = 1.0  # Give more weight to most recent

        total_weight = sum(weights)
        fused = [0.0, 0.0, 0.0]

        for pos, w in zip(positions, weights):
            for i in range(3):
                fused[i] += pos[i] * w

        return tuple(f / total_weight for f in fused)

    def _weighted_fuse_orientations(self, orientations: List[Tuple], weight: float) -> Tuple:
        """Fuse multiple orientation estimates."""
        if not orientations:
            return (1.0, 0.0, 0.0, 0.0)  # Identity quaternion

        if len(orientations) == 1:
            return orientations[0]

        # For quaternions, we need special averaging
        # Simplified: just take the most recent
        return orientations[-1]

    async def _add_measurement(self, measurement: SensorMeasurement):
        """Add a measurement to the buffer."""
        self.measurement_buffer.append(measurement)

    async def _on_camera_measurement(self, event):
        """Handle camera image measurements."""
        if 'image' in event:
            measurement = SensorMeasurement(
                sensor_type="camera",
                timestamp=asyncio.get_event_loop().time(),
                data=event['image'],
                confidence=0.8
            )
            await self._add_measurement(measurement)

    async def _on_depth_measurement(self, event):
        """Handle depth sensor measurements."""
        if 'reading' in event:
            measurement = SensorMeasurement(
                sensor_type="depth",
                timestamp=asyncio.get_event_loop().time(),
                data=event['reading'],
                confidence=0.9
            )
            await self._add_measurement(measurement)

    async def _on_detection_measurement(self, event):
        """Handle object detection measurements."""
        if 'detections' in event:
            measurement = SensorMeasurement(
                sensor_type="detection",
                timestamp=asyncio.get_event_loop().time(),
                data=event['detections'],
                confidence=0.7
            )
            await self._add_measurement(measurement)

    async def _on_gps_measurement(self, event):
        """Handle GPS measurements."""
        if 'msg' in event:
            measurement = SensorMeasurement(
                sensor_type="gps",
                timestamp=asyncio.get_event_loop().time(),
                data=event['msg'],
                confidence=0.95
            )
            await self._add_measurement(measurement)

    async def _on_imu_measurement(self, event):
        """Handle IMU measurements."""
        if 'msg' in event:
            measurement = SensorMeasurement(
                sensor_type="imu",
                timestamp=asyncio.get_event_loop().time(),
                data=event['msg'],
                confidence=0.9
            )
            await self._add_measurement(measurement)

    def _get_fused_state(self) -> Dict:
        """Get current fused state as dictionary."""
        if self.fused_state is None:
            return {"status": "no_data"}

        return {
            "timestamp": self.fused_state.timestamp,
            "position": self.fused_state.position,
            "velocity": self.fused_state.velocity,
            "orientation": self.fused_state.orientation,
            "confidence": self.fused_state.confidence,
            "sensors_used": self.fused_state.sensors_used,
        }