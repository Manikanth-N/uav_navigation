"""Protocol abstraction layer for UAV SDK.

Phase 2: Provide a unified interface for multiple communication
protocols (MAVLink, ROS2, custom links).
"""

import asyncio
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any, Dict, Optional


class ProtocolCategory(Enum):
    """Standard protocol categories."""
    MAVLINK = auto()
    ROS2 = auto()
    CUSTOM = auto()


class ProtocolInterface(ABC):
    """Abstract protocol adapter interface."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._connected = False
        self._status = "initialized"

    @abstractmethod
    async def connect(self) -> bool:
        """Establish protocol connection."""

    @abstractmethod
    async def disconnect(self) -> bool:
        """Tear down protocol connection."""

    @abstractmethod
    async def send(self, data: Any) -> bool:
        """Send a protocol message/data."""

    @abstractmethod
    async def receive(self, timeout: float = 0.1) -> Optional[Any]:
        """Receive a protocol message/data."""

    def is_connected(self) -> bool:
        """Return current connection status."""
        return self._connected

    def get_status(self) -> str:
        """Return current adapter status."""
        return self._status

    def update_status(self, status: str) -> None:
        """Update adapter status message."""
        self._status = status
