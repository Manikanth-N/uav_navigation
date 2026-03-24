"""
Thread-safe vehicle state management with MVCC.

Maintains vehicle state with version tracking for consistency.
"""

import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class VehicleState:
    """Current vehicle state snapshot."""
    
    # Basic info
    timestamp: float = 0.0
    
    # Position/Location
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0
    relative_alt: float = 0.0
    
    # Attitude (roll, pitch, yaw in radians)
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    
    # Velocity (m/s)
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    ground_speed: float = 0.0
    
    # System status
    armed: bool = False
    mode: str = "UNKNOWN"
    system_status: str = "UNKNOWN"  # e.g., "ACTIVE", "CRITICAL"
    
    # Power
    battery_percent: float = 100.0
    battery_voltage: float = 0.0
    battery_current: float = 0.0
    
    # Sensors
    is_armable: bool = False
    has_gps: bool = False
    gps_status: int = 0  # 0=no fix, 1=2D fix, 2=3D fix, 3=RTK fix
    
    # Custom fields from plugins
    custom: Dict[str, Any] = field(default_factory=dict)


class UAVState:
    """Thread-safe vehicle state management with MVCC.
    
    Maintains current vehicle state and version history for
    consistency and change tracking.
    """
    
    def __init__(self):
        """Initialize state manager."""
        self._lock = threading.RLock()
        self._state = VehicleState()
        self._version = 0
        self._change_listeners: List[Callable] = []
        self._history: List[VehicleState] = []
        self._max_history = 100
    
    def get(self) -> VehicleState:
        """Get current state snapshot (thread-safe).
        
        Returns a copy to prevent external modifications.
        
        Returns:
            Copy of current VehicleState
        """
        with self._lock:
            # Return copy of current state
            state_dict = asdict(self._state)
            return VehicleState(**state_dict)
    
    def update(self, **kwargs) -> int:
        """Update state fields atomically.
        
        Returns new version number.
        
        Args:
            **kwargs: State fields to update
            
        Returns:
            New version number
        """
        with self._lock:
            # Validate fields
            for key in kwargs.keys():
                if not hasattr(self._state, key):
                    logger.warning(f"Unknown state field: {key}")
            
            # Update fields
            for key, value in kwargs.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)
            
            # Increment version
            self._version += 1
            
            # Keep in history
            state_copy = VehicleState(**asdict(self._state))
            self._history.append(state_copy)
            if len(self._history) > self._max_history:
                self._history.pop(0)
            
            # Notify listeners
            for listener in self._change_listeners:
                try:
                    listener(self._state)
                except Exception as e:
                    logger.error(f"Error in state listener: {e}")
            
            logger.debug(f"State updated (v{self._version}): {list(kwargs.keys())}")
            return self._version
    
    def get_version(self) -> int:
        """Get current state version number.
        
        Returns:
            Version number
        """
        with self._lock:
            return self._version
    
    def subscribe(self, callback: Callable) -> None:
        """Subscribe to state changes.
        
        Callback will be called whenever state changes.
        
        Args:
            callback: Function(state) called on change
        """
        with self._lock:
            self._change_listeners.append(callback)
    
    def unsubscribe(self, callback: Callable) -> bool:
        """Unsubscribe from state changes.
        
        Args:
            callback: Callback to remove
            
        Returns:
            True if was subscribed
        """
        with self._lock:
            try:
                self._change_listeners.remove(callback)
                return True
            except ValueError:
                return False
    
    def get_history(self, count: int = 10) -> List[VehicleState]:
        """Get last N state snapshots.
        
        Args:
            count: Number of snapshots to return
            
        Returns:
            List of historical states
        """
        with self._lock:
            return self._history[-count:]
    
    def are_gps_coordinates_valid(self) -> bool:
        """Check if GPS coordinates are valid.
        
        Returns:
            True if lat/lon are non-zero
        """
        state = self.get()
        return state.lat != 0.0 and state.lon != 0.0
    
    def get_position_tuple(self) -> tuple:
        """Get position as (lat, lon, alt) tuple.
        
        Returns:
            Tuple of (latitude, longitude, altitude)
        """
        state = self.get()
        return (state.lat, state.lon, state.alt)
    
    def get_attitude_tuple(self) -> tuple:
        """Get attitude as (roll, pitch, yaw) tuple.
        
        Returns:
            Tuple of (roll, pitch, yaw) in radians
        """
        state = self.get()
        return (state.roll, state.pitch, state.yaw)
    
    def get_velocity_tuple(self) -> tuple:
        """Get velocity as (vx, vy, vz) tuple.
        
        Returns:
            Tuple of (vx, vy, vz) velocities in m/s
        """
        state = self.get()
        return (state.vx, state.vy, state.vz)
    
    def reset(self) -> None:
        """Reset state to default values."""
        with self._lock:
            self._state = VehicleState()
            self._version = 0
            self._history.clear()
            logger.info("State reset to defaults")