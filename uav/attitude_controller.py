# attitude_controller.py
import math


class AttitudeController:
    def __init__(self, roll_deg=0, pitch_deg=0, yaw_deg=0, thrust=0.5,
                 roll_limit=0, pitch_limit=0, yaw_limit=0, thrust_min=0.0, thrust_max=1.0):
        """
        Initialize attitude controller with configurable limits.
        limit=0 means NO LIMIT (unbounded).
        
        Args:
            roll_deg, pitch_deg, yaw_deg: Initial attitude in degrees
            thrust: Initial thrust (0.0 to 1.0)
            roll_limit, pitch_limit, yaw_limit: 0=no limit, else ±limit degrees
            thrust_min, thrust_max: Thrust bounds (0=no lower limit)
        """
        # Store limits (0 = no limit)
        self.roll_limit = roll_limit
        self.pitch_limit = pitch_limit  
        self.yaw_limit = yaw_limit
        self.thrust_min = thrust_min
        self.thrust_max = thrust_max
        
        # Initialize values (only clamp if limits > 0)
        self.roll_deg = self._clamp_value(roll_deg, self.roll_limit)
        self.pitch_deg = self._clamp_value(pitch_deg, self.pitch_limit)
        self.yaw_deg = self._clamp_value(yaw_deg, self.yaw_limit)
        self.thrust = self._clamp_thrust(thrust, self.thrust_min, self.thrust_max)

    def _clamp_value(self, value, limit):
        """Clamp value if limit > 0, else return as-is."""
        if limit > 0:
            return max(-limit, min(limit, value))
        return value  # No limit

    def _clamp_thrust(self, value, min_val, max_val):
        """Clamp thrust if bounds > 0."""
        if min_val > 0:
            value = max(min_val, value)
        if max_val > 0:
            value = min(max_val, value)
        return value

    def update_roll(self, delta_deg):
        """Update roll, respecting roll_limit if > 0."""
        self.roll_deg = self._clamp_value(self.roll_deg + delta_deg, self.roll_limit)

    def update_pitch(self, delta_deg):
        """Update pitch, respecting pitch_limit if > 0."""
        self.pitch_deg = self._clamp_value(self.pitch_deg + delta_deg, self.pitch_limit)

    def update_yaw(self, delta_deg):
        """Update yaw, respecting yaw_limit if > 0."""
        self.yaw_deg = self._clamp_value(self.yaw_deg + delta_deg, self.yaw_limit)

    def update_thrust(self, delta):
        """Update thrust, respecting thrust_min/max if > 0."""
        self.thrust = self._clamp_thrust(self.thrust + delta, self.thrust_min, self.thrust_max)

    def set_roll(self, roll_deg):
        """Directly set roll value (clamped if limit > 0)."""
        self.roll_deg = self._clamp_value(roll_deg, self.roll_limit)

    def set_pitch(self, pitch_deg):
        """Directly set pitch value (clamped if limit > 0)."""
        self.pitch_deg = self._clamp_value(pitch_deg, self.pitch_limit)

    def set_yaw(self, yaw_deg):
        """Directly set yaw value (clamped if limit > 0)."""
        self.yaw_deg = self._clamp_value(yaw_deg, self.yaw_limit)

    def set_thrust(self, thrust):
        """Directly set thrust value (clamped if bounds > 0)."""
        self.thrust = self._clamp_thrust(thrust, self.thrust_min, self.thrust_max)

    def get_attitude_quaternion(self):
        """Convert current attitude to quaternion."""
        roll = math.radians(self.roll_deg)
        pitch = math.radians(self.pitch_deg)
        yaw = math.radians(self.yaw_deg)

        t0 = math.cos(yaw * 0.5)
        t1 = math.sin(yaw * 0.5)
        t2 = math.cos(roll * 0.5)
        t3 = math.sin(roll * 0.5)
        t4 = math.cos(pitch * 0.5)
        t5 = math.sin(pitch * 0.5)

        w = t0 * t2 * t4 + t1 * t3 * t5
        x = t0 * t3 * t4 - t1 * t2 * t5
        y = t0 * t2 * t5 + t1 * t3 * t4
        z = t1 * t2 * t4 - t0 * t3 * t5

        return [w, x, y, z]

    def get_state(self):
        """Get current state with limit status."""
        limits = {
            'roll': '∞' if self.roll_limit == 0 else f"±{self.roll_limit}°",
            'pitch': '∞' if self.pitch_limit == 0 else f"±{self.pitch_limit}°", 
            'yaw': '∞' if self.yaw_limit == 0 else f"±{self.yaw_limit}°",
            'thrust': f"{self.thrust_min}-{self.thrust_max}" if self.thrust_min > 0 or self.thrust_max > 0 else '∞'
        }
        return {
            'roll': self.roll_deg,
            'pitch': self.pitch_deg,
            'yaw': self.yaw_deg,
            'thrust': self.thrust,
            'limits': limits
        }

    def reset(self):
        """Reset to zero attitude, mid-thrust."""
        self.roll_deg = 0
        self.pitch_deg = 0
        self.yaw_deg = 0
        self.thrust = 0.5
