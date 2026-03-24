"""
Tests for perception plugins.
"""

import pytest
import asyncio
import numpy as np
import cv2
from unittest.mock import Mock, AsyncMock, patch

from uav_sdk.plugins.perception.camera import CameraPlugin
from uav_sdk.plugins.perception.object_detection import ObjectDetectionPlugin, Detection
from uav_sdk.plugins.perception.depth_sensor import DepthSensorPlugin, DepthReading
from uav_sdk.plugins.perception.sensor_fusion import SensorFusionPlugin, SensorMeasurement


class TestCameraPlugin:
    """Test camera plugin functionality."""

    @pytest.fixture
    def mock_runtime(self):
        """Create mock runtime."""
        runtime = Mock()
        runtime.event_system = Mock()
        runtime.event_system.publish = AsyncMock()
        return runtime

    @pytest.fixture
    def camera_plugin(self, mock_runtime):
        """Create camera plugin instance."""
        config = {
            "camera": {
                "device_id": 0,
                "width": 320,
                "height": 240,
                "fps": 15,
                "auto_exposure": True,
            },
            "stream_enabled": False,
        }
        return CameraPlugin(config, mock_runtime)

    @pytest.mark.asyncio
    async def test_initialization(self, camera_plugin, mock_runtime):
        """Test camera plugin initialization."""
        with patch('cv2.VideoCapture') as mock_capture:
            mock_cap = Mock()
            mock_cap.isOpened.return_value = True
            mock_cap.get.side_effect = lambda prop: {
                3: 320,  # CAP_PROP_FRAME_WIDTH
                4: 240,  # CAP_PROP_FRAME_HEIGHT
                5: 15,   # CAP_PROP_FPS
            }.get(prop, 0)
            mock_capture.return_value = mock_cap

            success = await camera_plugin.initialize()
            assert success
            assert camera_plugin.state.value == "initialized"

    @pytest.mark.asyncio
    async def test_read_sensor(self, camera_plugin):
        """Test reading image from camera."""
        await camera_plugin.initialize()

        # Mock camera capture
        with patch.object(camera_plugin, 'capture') as mock_capture:
            mock_capture.isOpened.return_value = True
            mock_frame = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
            mock_capture.read.return_value = (True, mock_frame)

            result = await camera_plugin.read_sensor("image")
            assert result is not None
            assert isinstance(result, np.ndarray)
            assert result.shape == (240, 320, 3)

    @pytest.mark.asyncio
    async def test_write_actuator(self, camera_plugin):
        """Test camera control settings."""
        await camera_plugin.initialize()

        with patch.object(camera_plugin, 'capture') as mock_capture:
            mock_capture.return_value = Mock()

            # Test exposure control
            success = await camera_plugin.write_actuator("exposure", 50)
            assert success
            mock_capture.set.assert_called_with(15, 50)  # CAP_PROP_EXPOSURE

    def test_get_camera_info(self, camera_plugin):
        """Test getting camera information."""
        # Initialize camera with mock
        with patch('cv2.VideoCapture') as mock_capture:
            mock_cap = Mock()
            mock_cap.isOpened.return_value = True
            mock_cap.get.side_effect = lambda prop: {
                3: 320,  # CAP_PROP_FRAME_WIDTH
                4: 240,  # CAP_PROP_FRAME_HEIGHT
                5: 15,   # CAP_PROP_FPS
            }.get(prop, 0)
            mock_capture.return_value = mock_cap
            camera_plugin.capture = mock_cap

            info = camera_plugin.get_camera_info()
            assert "device_id" in info
            assert "resolution" in info
            assert info["streaming"] == False


class TestObjectDetectionPlugin:
    """Test object detection plugin functionality."""

    @pytest.fixture
    def mock_runtime(self):
        """Create mock runtime."""
        runtime = Mock()
        runtime.event_system = Mock()
        runtime.event_system.publish = AsyncMock()
        return runtime

    @pytest.fixture
    def detection_plugin(self, mock_runtime):
        """Create object detection plugin instance."""
        config = {
            "model": {
                "config_path": "models/yolov3.cfg",
                "weights_path": "models/yolov3.weights",
                "classes_path": "models/coco.names",
            },
            "confidence_threshold": 0.5,
            "input_size": 320,
        }
        return ObjectDetectionPlugin(config, mock_runtime)

    @pytest.mark.asyncio
    async def test_initialization(self, detection_plugin, mock_runtime):
        """Test object detection plugin initialization."""
        with patch('cv2.dnn.readNetFromDarknet') as mock_net, \
             patch('builtins.open', create=True) as mock_open:

            mock_net.return_value = Mock()
            mock_file = Mock()
            mock_file.readlines.return_value = ["class1\n", "class2\n"]
            mock_open.return_value.__enter__.return_value = mock_file

            success = await detection_plugin.initialize()
            assert success
            assert len(detection_plugin.classes) == 2

    @pytest.mark.asyncio
    async def test_process_image(self, detection_plugin):
        """Test processing image for detections."""
        await detection_plugin.initialize()

        # Create test image
        test_image = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)

        # Mock the neural network
        with patch.object(detection_plugin, 'net') as mock_net:
            mock_net.getUnconnectedOutLayers.return_value = [1, 2, 3]
            mock_net.getLayerNames.return_value = ["layer1", "layer2", "layer3"]
            # Mock forward pass with empty results (no detections)
            mock_net.forward.return_value = [np.zeros((1, 85))]

            result = await detection_plugin.process(test_image)
            assert "detections" in result
            assert isinstance(result["detections"], list)


class TestDepthSensorPlugin:
    """Test depth sensor plugin functionality."""

    @pytest.fixture
    def mock_runtime(self):
        """Create mock runtime."""
        runtime = Mock()
        runtime.event_system = Mock()
        runtime.event_system.publish = AsyncMock()
        return runtime

    @pytest.fixture
    def depth_plugin(self, mock_runtime):
        """Create depth sensor plugin instance."""
        config = {
            "sensor_type": "stereo",
            "max_range": 10.0,
            "min_range": 0.1,
            "resolution": "320x240",
        }
        return DepthSensorPlugin(config, mock_runtime)

    @pytest.mark.asyncio
    async def test_initialization(self, depth_plugin):
        """Test depth sensor plugin initialization."""
        success = await depth_plugin.initialize()
        assert success
        assert depth_plugin.state.value == "initialized"

    @pytest.mark.asyncio
    async def test_read_depth_map(self, depth_plugin):
        """Test reading depth map."""
        await depth_plugin.initialize()

        result = await depth_plugin.read_sensor("depth")
        assert result is not None
        assert isinstance(result, DepthReading)
        assert hasattr(result, 'depth_map')
        assert result.depth_map.shape == (240, 320)  # Based on resolution

    @pytest.mark.asyncio
    async def test_read_pointcloud(self, depth_plugin):
        """Test reading point cloud."""
        await depth_plugin.initialize()

        result = await depth_plugin.read_sensor("pointcloud")
        assert result is not None
        assert isinstance(result, np.ndarray)

    def test_detect_obstacles(self, depth_plugin):
        """Test obstacle detection."""
        # Create test depth map with obstacle
        depth_map = np.full((100, 100), 5.0, dtype=np.float32)
        cv2.rectangle(depth_map, (40, 40), (60, 60), 1.0, -1)  # Close obstacle

        obstacles = depth_plugin.detect_obstacles(depth_map, threshold=2.0)
        assert len(obstacles) > 0  # Should detect the rectangle


class TestSensorFusionPlugin:
    """Test sensor fusion plugin functionality."""

    @pytest.fixture
    def mock_runtime(self):
        """Create mock runtime."""
        runtime = Mock()
        runtime.event_system = Mock()
        runtime.event_system.publish = AsyncMock()
        return runtime

    @pytest.fixture
    def fusion_plugin(self, mock_runtime):
        """Create sensor fusion plugin instance."""
        config = {
            "fusion_method": "weighted_average",
            "fusion_rate": 10.0,
        }
        return SensorFusionPlugin(config, mock_runtime)

    @pytest.mark.asyncio
    async def test_initialization(self, fusion_plugin):
        """Test sensor fusion plugin initialization."""
        success = await fusion_plugin.initialize()
        assert success
        assert fusion_plugin.state.value == "initialized"

    @pytest.mark.asyncio
    async def test_add_measurement(self, fusion_plugin):
        """Test adding sensor measurements."""
        await fusion_plugin.initialize()

        measurement = SensorMeasurement(
            sensor_type="gps",
            timestamp=asyncio.get_event_loop().time(),
            data=Mock(lat=37.7749e7, lon=-122.4194e7, alt=20000),  # MAVLink format
            confidence=0.95
        )

        await fusion_plugin._add_measurement(measurement)
        assert len(fusion_plugin.measurement_buffer) == 1

    @pytest.mark.asyncio
    async def test_get_fused_state(self, fusion_plugin):
        """Test getting fused state."""
        await fusion_plugin.initialize()

        state = fusion_plugin._get_fused_state()
        assert "timestamp" in state
        assert "position" in state
        assert "confidence" in state

    @pytest.mark.asyncio
    async def test_gps_measurement_handling(self, fusion_plugin):
        """Test GPS measurement event handling."""
        await fusion_plugin.initialize()

        # Mock GPS message
        mock_msg = Mock()
        mock_msg.lat = 377749000  # 37.7749 * 1e7
        mock_msg.lon = -1224194000  # -122.4194 * 1e7
        mock_msg.alt = 20000  # 20m * 1000

        mock_event = {"msg": mock_msg}  # Use dict instead of Mock

        await fusion_plugin._on_gps_measurement(mock_event)
        assert len(fusion_plugin.measurement_buffer) == 1

    def test_weighted_fuse_positions(self, fusion_plugin):
        """Test position fusion."""
        positions = [(1.0, 2.0, 3.0), (1.1, 2.1, 3.1)]
        fused = fusion_plugin._weighted_fuse_positions(positions, 0.7)

        assert len(fused) == 3
        assert fused[0] > 1.0 and fused[0] < 1.1  # Should be weighted average