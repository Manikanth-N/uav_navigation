import time
import math
from pymavlink.dialects.v20 import common as mavlink2
import threading

class Gimbal:

    def __init__(self, uav):
        self.uav = uav
        self.device_id = None

        self.pitch_min = None
        self.pitch_max = None
        self.yaw_min = None
        self.yaw_max = None

        self.roll = 0
        self.pitch = 0
        self.yaw = 0

        self.ready = False

        self.auto_sync = True
        self._sync_thread_running = False

    # ==================================================
    # PUBLIC START (DISCOVER + HANDSHAKE)
    # ==================================================
    def start(self):
        if not self._discover():
            raise RuntimeError("Gimbal discovery failed")

        self._load_limits()
        self._take_control()
        self._request_attitude_stream(10)

        if not self._sync_from_device(timeout=5):
            print("Warning: Could not sync from device")

        self.ready = True

        # Start background auto-sync
        self._start_auto_sync_thread()

        print("Gimbal ready")

    # ==================================================
    # PUBLIC MOVEMENT API
    # ==================================================
    def move_up(self, deg=5):
        self._move(d_pitch=deg)

    def move_down(self, deg=5):
        self._move(d_pitch=-deg)

    def move_left(self, deg=5):
        self._move(d_yaw=-deg)

    def move_right(self, deg=5):
        self._move(d_yaw=deg)

    def center(self):
        self.set_absolute(0, 0, 0)

    def set_absolute(self, roll, pitch, yaw):
        self._ensure_ready()

        # Sync first (important)
        self._sync_from_device()

        self.roll = roll
        self.pitch = pitch
        self.yaw = self._wrap(yaw)

        self._apply_limits()
        self._send()

    # ==================================================
    # INTERNAL MOVE
    # ==================================================
    def _move(self, d_roll=0, d_pitch=0, d_yaw=0):
        self._ensure_ready()

        # Always sync before applying delta
        self._sync_from_device()

        self.roll += d_roll
        self.pitch += d_pitch
        self.yaw += d_yaw

        self.yaw = self._wrap(self.yaw)
        self._apply_limits()
        self._send()

    # ==================================================
    # DISCOVERY + HANDSHAKE
    # ==================================================
    def _discover(self, timeout=3):

        master = self.uav.connection.master

        master.mav.command_long_send(
            self.uav.connection.system_id,
            self.uav.connection.component_id,
            mavlink2.MAV_CMD_REQUEST_MESSAGE,
            0,
            mavlink2.MAVLINK_MSG_ID_GIMBAL_MANAGER_INFORMATION,
            0,0,0,0,0,0
        )

        start = time.time()

        while time.time() - start < timeout:
            msg = self.uav.connection.dispatcher.latest(
                "GIMBAL_MANAGER_INFORMATION"
            )
            if msg:
                self.device_id = msg.gimbal_device_id
                return True
            time.sleep(0.05)

        return False

    def _take_control(self):

        master = self.uav.connection.master

        master.mav.command_long_send(
            self.uav.connection.system_id,
            self.uav.connection.component_id,
            mavlink2.MAV_CMD_DO_GIMBAL_MANAGER_CONFIGURE,
            0,
            master.source_system,
            master.source_component,
            0,0,
            self.device_id,
            0,0
        )

    def release(self):

        master = self.uav.connection.master

        master.mav.command_long_send(
            self.uav.connection.system_id,
            self.uav.connection.component_id,
            mavlink2.MAV_CMD_DO_GIMBAL_MANAGER_CONFIGURE,
            0,
            0,0,0,0,
            self.device_id,
            0,0
        )

    def _load_limits(self):

        self.pitch_min = self.uav.get_param("MNT1_PITCH_MIN")
        self.pitch_max = self.uav.get_param("MNT1_PITCH_MAX")
        self.yaw_min   = self.uav.get_param("MNT1_YAW_MIN")
        self.yaw_max   = self.uav.get_param("MNT1_YAW_MAX")

    def _sync_from_device(self, timeout=3):
        start = time.time()

        while time.time() - start < timeout:

            msg = self.uav.connection.dispatcher.latest(
                "GIMBAL_DEVICE_ATTITUDE_STATUS"
            )

            if not msg:
                time.sleep(0.05)
                continue

            if msg.gimbal_device_id != self.device_id:
                time.sleep(0.05)
                continue

            r, p, y = self._quat_to_euler(msg.q)

            self.roll = r
            self.pitch = p
            self.yaw = self._wrap(y)

            return True

        return False

    # ==================================================
    # INTERNAL SEND
    # ==================================================
    def _send(self):

        master = self.uav.connection.master

        q = self._euler_to_quaternion(
            math.radians(self.roll),
            math.radians(self.pitch),
            math.radians(self.yaw)
        )

        master.mav.gimbal_manager_set_attitude_send(
            self.uav.connection.system_id,
            self.uav.connection.component_id,
            mavlink2.GIMBAL_MANAGER_FLAGS_YAW_IN_VEHICLE_FRAME,
            self.device_id,
            q,
            float("nan"),
            float("nan"),
            float("nan")
        )

    # ==================================================
    # UTILITIES
    # ==================================================
    def _ensure_ready(self):
        if not self.ready:
            raise RuntimeError("Gimbal not started. Call start() first.")

    def _apply_limits(self):
        self.pitch = self._clamp(self.pitch, self.pitch_min, self.pitch_max)
        self.yaw = self._clamp(self.yaw, self.yaw_min, self.yaw_max)

    def _wrap(self, angle):
        return (angle + 180) % 360 - 180

    def _clamp(self, val, min_val, max_val):
        if min_val is None or max_val is None:
            return val
        return max(min(val, max_val), min_val)

    def _euler_to_quaternion(self, roll, pitch, yaw):
        cy = math.cos(yaw * 0.5)
        sy = math.sin(yaw * 0.5)
        cp = math.cos(pitch * 0.5)
        sp = math.sin(pitch * 0.5)
        cr = math.cos(roll * 0.5)
        sr = math.sin(roll * 0.5)

        return [
            cr * cp * cy + sr * sp * sy,
            sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy,
        ]

    def _quat_to_euler(self, q):
        w, x, y, z = q
        t0 = 2*(w*x + y*z)
        t1 = 1-2*(x*x + y*y)
        roll = math.atan2(t0, t1)

        t2 = 2*(w*y - z*x)
        t2 = max(min(t2, 1), -1)
        pitch = math.asin(t2)

        t3 = 2*(w*z + x*y)
        t4 = 1-2*(y*y + z*z)
        yaw = math.atan2(t3, t4)

        return (
            math.degrees(roll),
            math.degrees(pitch),
            math.degrees(yaw),
        )
    
    def _request_attitude_stream(self, rate_hz=10):

        master = self.uav.connection.master

        master.mav.command_long_send(
            self.uav.connection.system_id,
            self.uav.connection.component_id,
            mavlink2.MAV_CMD_SET_MESSAGE_INTERVAL,
            0,
            mavlink2.MAVLINK_MSG_ID_GIMBAL_DEVICE_ATTITUDE_STATUS,
            int(1e6 / rate_hz),   # microseconds
            0,0,0,0,0
        )
    
    def debug_print_sync(self):
        msg = self.uav.connection.dispatcher.latest(
            "GIMBAL_DEVICE_ATTITUDE_STATUS"
        )
        print("Debug: Latest GIMBAL_DEVICE_ATTITUDE_STATUS:", msg)
        if not msg:
            print("No GIMBAL_DEVICE_ATTITUDE_STATUS received")
            return

        d_roll, d_pitch, d_yaw = self._quat_to_euler(msg.q)

        i_roll = self.roll
        i_pitch = self.pitch
        i_yaw = self.yaw

        # Normalize yaw
        d_yaw = self._wrap(d_yaw)
        i_yaw = self._wrap(i_yaw)

        diff_roll = d_roll - i_roll
        diff_pitch = d_pitch - i_pitch
        diff_yaw = (d_yaw - i_yaw + 180) % 360 - 180

        print("\n========== GIMBAL SYNC CHECK ==========")
        print(f"Device   -> Roll:{d_roll:7.2f}  Pitch:{d_pitch:7.2f}  Yaw:{d_yaw:7.2f}")
        print(f"Internal -> Roll:{i_roll:7.2f}  Pitch:{i_pitch:7.2f}  Yaw:{i_yaw:7.2f}")
        print(f"Diff     -> Roll:{diff_roll:7.2f}  Pitch:{diff_pitch:7.2f}  Yaw:{diff_yaw:7.2f}")
        print("=======================================\n")

    

    def _start_auto_sync_thread(self):
        if self._sync_thread_running:
            return

        import threading

        self._sync_thread_running = True

        threading.Thread(
            target=self._auto_sync_loop,
            daemon=True
        ).start()


    def _auto_sync_loop(self):
        while self.ready:
            if self.auto_sync:
                self._sync_from_device(timeout=0.1)
            time.sleep(0.05)