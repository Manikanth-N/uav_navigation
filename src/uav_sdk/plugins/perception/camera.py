"""
Camera plugin for UAV perception.

Provides camera interface and image capture capabilities.
"""

from typing import Any, Dict, Optional, Tuple
import asyncio
import cv2
import numpy as np
import logging
from dataclasses import dataclass

from uav_sdk.plugins.base import DriverPlugin, PluginInfo, PluginState

logger = logging.getLogger(__name__)


@dataclass
class CameraConfig:
    """Camera configuration parameters."""
    device_id: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30
    format: str = "MJPEG"  # MJPEG, YUYV, etc.
    auto_exposure: bool = True
    exposure: int = 100
    gain: int = 50


class CameraPlugin(DriverPlugin):
    """Camera driver plugin for image capture."""

    def __init__(self, config: Dict[str, Any], runtime):
        super().__init__(config, runtime)
        self.camera_config = CameraConfig(**config.get("camera", {}))
        self.capture = None
        self.is_streaming = False
        self._stream_task = None

    def get_info(self):
        return PluginInfo(
            name="camera",
            version="0.1.0",
            author="SDK Team",
            description="Camera interface and image capture",
            plugin_type="perception",
            dependencies=[],
            features=["image_capture", "video_stream", "camera_control"],
            config_schema={
                "camera": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "integer", "default": 0},
                        "width": {"type": "integer", "default": 640},
                        "height": {"type": "integer", "default": 480},
                        "fps": {"type": "integer", "default": 30},
                        "format": {"type": "string", "default": "MJPEG"},
                        "auto_exposure": {"type": "boolean", "default": True},
                        "exposure": {"type": "integer", "default": 100},
                        "gain": {"type": "integer", "default": 50},
                    }
                },
                "stream_enabled": {"type": "boolean", "default": False},
                "stream_interval": {"type": "number", "default": 0.1},
            },
        )

    async def initialize(self) -> bool:
        try:
            # Initialize camera
            self.capture = cv2.VideoCapture(self.camera_config.device_id)

            if not self.capture.isOpened():
                logger.error(f"Failed to open camera device {self.camera_config.device_id}")
                return False

            # Set camera properties
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_config.width)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_config.height)
            self.capture.set(cv2.CAP_PROP_FPS, self.camera_config.fps)

            # Set exposure and gain
            if not self.camera_config.auto_exposure:
                self.capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)
                self.capture.set(cv2.CAP_PROP_EXPOSURE, self.camera_config.exposure)
                self.capture.set(cv2.CAP_PROP_GAIN, self.camera_config.gain)

            # Verify settings
            actual_width = self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = self.capture.get(cv2.CAP_PROP_FPS)

            logger.info(f"Camera initialized: {actual_width}x{actual_height} @ {actual_fps}fps")

            self.state = PluginState.INITIALIZED
            return True

        except Exception as e:
            logger.error(f"Camera initialization failed: {e}")
            return False

    async def start(self) -> bool:
        if self.config.get("stream_enabled", False):
            self._stream_task = asyncio.create_task(self._stream_images())
            logger.info("Camera streaming started")

        self.state = PluginState.STARTED
        return True

    async def shutdown(self) -> bool:
        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass

        if self.capture:
            self.capture.release()

        self.state = PluginState.STOPPED
        logger.info("Camera shutdown")
        return True

    async def read_sensor(self, sensor_id: str) -> Any:
        """Read image from camera.

        Args:
            sensor_id: "image" for current frame

        Returns:
            Image data as numpy array
        """
        if sensor_id != "image":
            return None

        if not self.capture or not self.capture.isOpened():
            logger.error("Camera not available")
            return None

        ret, frame = self.capture.read()
        if not ret:
            logger.warning("Failed to capture frame")
            return None

        return frame

    async def write_actuator(self, actuator_id: str, value: Any) -> bool:
        """Control camera settings.

        Args:
            actuator_id: Setting to control ("exposure", "gain", "focus")
            value: New value

        Returns:
            True if successful
        """
        if not self.capture:
            return False

        try:
            if actuator_id == "exposure":
                self.capture.set(cv2.CAP_PROP_EXPOSURE, value)
            elif actuator_id == "gain":
                self.capture.set(cv2.CAP_PROP_GAIN, value)
            elif actuator_id == "focus":
                self.capture.set(cv2.CAP_PROP_FOCUS, value)
            elif actuator_id == "brightness":
                self.capture.set(cv2.CAP_PROP_BRIGHTNESS, value)
            elif actuator_id == "contrast":
                self.capture.set(cv2.CAP_PROP_CONTRAST, value)
            else:
                logger.warning(f"Unknown camera control: {actuator_id}")
                return False

            logger.debug(f"Set {actuator_id} to {value}")
            return True

        except Exception as e:
            logger.error(f"Failed to set {actuator_id}: {e}")
            return False

    async def _stream_images(self):
        """Continuously stream images as events."""
        interval = self.config.get("stream_interval", 0.1)

        try:
            while self.is_streaming and self.state == PluginState.STARTED:
                frame = await self.read_sensor("image")
                if frame is not None:
                    # Publish image event
                    await self.runtime.event_system.publish("camera.image", image=frame)

                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            logger.info("Image streaming cancelled")
        except Exception as e:
            logger.error(f"Image streaming error: {e}")

    def get_camera_info(self) -> Dict:
        """Get camera information and current settings."""
        if not self.capture:
            return {"status": "not_initialized"}

        return {
            "device_id": self.camera_config.device_id,
            "resolution": f"{self.camera_config.width}x{self.camera_config.height}",
            "fps": self.camera_config.fps,
            "actual_width": self.capture.get(cv2.CAP_PROP_FRAME_WIDTH),
            "actual_height": self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT),
            "actual_fps": self.capture.get(cv2.CAP_PROP_FPS),
            "auto_exposure": self.camera_config.auto_exposure,
            "streaming": self.is_streaming,
        }