"""
Object detection plugin for UAV perception.

Provides object detection capabilities using computer vision models.
"""

from typing import Any, Dict, List, Optional, Tuple
import asyncio
import cv2
import numpy as np
import logging
from dataclasses import dataclass

from uav_sdk.plugins.base import ComputePlugin, PluginInfo, PluginState

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """Object detection result."""
    class_id: int
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    center: Tuple[int, int]  # center x, y


class ObjectDetectionPlugin(ComputePlugin):
    """Object detection plugin using OpenCV DNN."""

    def __init__(self, config: Dict[str, Any], runtime):
        super().__init__(config, runtime)
        self.net = None
        self.classes = []
        self.colors = []
        self._detection_task = None
        self.last_detections: List[Detection] = []

    def get_info(self):
        return PluginInfo(
            name="object_detection",
            version="0.1.0",
            author="SDK Team",
            description="Object detection using computer vision models",
            plugin_type="perception",
            dependencies=["camera"],
            features=["object_detection", "real_time_processing", "confidence_filtering"],
            config_schema={
                "model": {
                    "type": "object",
                    "properties": {
                        "config_path": {"type": "string", "default": "models/yolov3.cfg"},
                        "weights_path": {"type": "string", "default": "models/yolov3.weights"},
                        "classes_path": {"type": "string", "default": "models/coco.names"},
                    }
                },
                "confidence_threshold": {"type": "number", "default": 0.5},
                "nms_threshold": {"type": "number", "default": 0.4},
                "input_size": {"type": "integer", "default": 416},
                "max_detections": {"type": "integer", "default": 10},
                "process_interval": {"type": "number", "default": 0.1},
            },
        )

    async def initialize(self) -> bool:
        try:
            model_config = self.config.get("model", {})

            # Load model files
            config_path = model_config.get("config_path", "models/yolov3.cfg")
            weights_path = model_config.get("weights_path", "models/yolov3.weights")
            classes_path = model_config.get("classes_path", "models/coco.names")

            # Load class names
            try:
                with open(classes_path, 'r') as f:
                    self.classes = [line.strip() for line in f.readlines()]
            except FileNotFoundError:
                logger.warning(f"Classes file not found: {classes_path}, using generic names")
                self.classes = [f"class_{i}" for i in range(80)]  # COCO has 80 classes

            # Load neural network
            self.net = cv2.dnn.readNetFromDarknet(config_path, weights_path)

            if self.net is None:
                logger.error("Failed to load neural network model")
                return False

            # Try to use GPU if available
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)

            # Generate random colors for each class
            np.random.seed(42)
            self.colors = np.random.randint(0, 255, size=(len(self.classes), 3), dtype=np.uint8)

            logger.info(f"Object detection initialized with {len(self.classes)} classes")
            self.state = PluginState.INITIALIZED
            return True

        except Exception as e:
            logger.error(f"Object detection initialization failed: {e}")
            return False

    async def start(self) -> bool:
        # Subscribe to camera images
        self.subscribe("camera.image", self._on_image_received)

        # Start processing task
        self._detection_task = asyncio.create_task(self._process_detections())
        logger.info("Object detection started")

        self.state = PluginState.STARTED
        return True

    async def shutdown(self) -> bool:
        if self._detection_task:
            self._detection_task.cancel()
            try:
                await self._detection_task
            except asyncio.CancelledError:
                pass

        self.state = PluginState.STOPPED
        logger.info("Object detection shutdown")
        return True

    async def process(self, input_data: Any) -> Any:
        """Process image for object detection.

        Args:
            input_data: Image data (numpy array) or dict with 'image' key

        Returns:
            List of Detection objects
        """
        if isinstance(input_data, dict) and 'image' in input_data:
            image = input_data['image']
        elif isinstance(input_data, np.ndarray):
            image = input_data
        else:
            return {"error": "Invalid input data"}

        detections = await self._detect_objects(image)
        self.last_detections = detections

        # Publish detection event
        await self.runtime.event_system.publish("detection.objects", detections=detections)

        return {
            "detections": [
                {
                    "class_id": d.class_id,
                    "class_name": d.class_name,
                    "confidence": d.confidence,
                    "bbox": d.bbox,
                    "center": d.center
                } for d in detections
            ]
        }

    async def _detect_objects(self, image: np.ndarray) -> List[Detection]:
        """Perform object detection on image."""
        if self.net is None or image is None:
            return []

        try:
            height, width = image.shape[:2]
            input_size = self.config.get("input_size", 416)

            # Create blob from image
            blob = cv2.dnn.blobFromImage(image, 1/255.0, (input_size, input_size),
                                       swapRB=True, crop=False)
            self.net.setInput(blob)

            # Get output layer names
            layer_names = self.net.getLayerNames()
            output_layers = [layer_names[i - 1] for i in self.net.getUnconnectedOutLayers()]

            # Forward pass
            outputs = self.net.forward(output_layers)

            # Process detections
            detections = []
            confidence_threshold = self.config.get("confidence_threshold", 0.5)
            nms_threshold = self.config.get("nms_threshold", 0.4)
            max_detections = self.config.get("max_detections", 10)

            boxes = []
            confidences = []
            class_ids = []

            for output in outputs:
                for detection in output:
                    scores = detection[5:]
                    class_id = np.argmax(scores)
                    confidence = scores[class_id]

                    if confidence > confidence_threshold:
                        # Scale bounding box coordinates
                        center_x = int(detection[0] * width)
                        center_y = int(detection[1] * height)
                        w = int(detection[2] * width)
                        h = int(detection[3] * height)

                        # Rectangle coordinates
                        x = int(center_x - w / 2)
                        y = int(center_y - h / 2)

                        boxes.append([x, y, w, h])
                        confidences.append(float(confidence))
                        class_ids.append(class_id)

            # Apply non-maximum suppression
            indices = cv2.dnn.NMSBoxes(boxes, confidences, confidence_threshold, nms_threshold)

            for i in indices:
                idx = i if isinstance(i, int) else i[0]
                if len(detections) >= max_detections:
                    break

                box = boxes[idx]
                x, y, w, h = box
                center_x = x + w // 2
                center_y = y + h // 2

                detection = Detection(
                    class_id=class_ids[idx],
                    class_name=self.classes[class_ids[idx]] if class_ids[idx] < len(self.classes) else "unknown",
                    confidence=confidences[idx],
                    bbox=(x, y, w, h),
                    center=(center_x, center_y)
                )
                detections.append(detection)

            return detections

        except Exception as e:
            logger.error(f"Object detection failed: {e}")
            return []

    async def _on_image_received(self, event):
        """Handle incoming camera images."""
        if 'image' in event:
            # Process the image for detections
            await self.process(event['image'])

    async def _process_detections(self):
        """Background task for continuous processing."""
        try:
            while self.state == PluginState.STARTED:
                await asyncio.sleep(self.config.get("process_interval", 0.1))
        except asyncio.CancelledError:
            logger.info("Detection processing cancelled")
        except Exception as e:
            logger.error(f"Detection processing error: {e}")

    def get_detection_stats(self) -> Dict:
        """Get detection statistics."""
        return {
            "last_detection_count": len(self.last_detections),
            "classes_detected": list(set(d.class_name for d in self.last_detections)),
            "avg_confidence": np.mean([d.confidence for d in self.last_detections]) if self.last_detections else 0.0,
        }