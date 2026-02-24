# vehicle.py
from pymavlink import mavutil
from pymavlink.dialects.v20 import common as mavlink2
import threading
import time


class UAV:

    ARDUCOPTER_MODES = {
        0: "STABILIZE", 1: "ACRO", 2: "ALT_HOLD", 3: "AUTO",
        4: "GUIDED", 5: "LOITER", 6: "RTL", 7: "CIRCLE",
        9: "LAND", 11: "DRIFT", 13: "SPORT", 14: "FLIP",
        15: "AUTOTUNE", 16: "POSHOLD", 17: "BRAKE",
        18: "THROW", 19: "AVOID_ADSB", 20: "GUIDED_NOGPS",
        21: "SMART_RTL", 22: "FLOWHOLD", 23: "FOLLOW",
        24: "ZIGZAG", 25: "SYSTEMID", 26: "AUTOROTATE",
        27: "AUTO_RTL", 28: "TURTLE"
    }

    def __init__(self, connection_string):
        self.connection_string = connection_string
        self.master = None

        self.fcu_system = None
        self.fcu_component = None
        self.firmware_type = None

        self.current_mode = None
        self.armed = False
        
        self.system_status = None
        self.vehicle_was_armed = False



        self._running = False
        self._lock = threading.Lock()

    # ---------------------------------------------------
    # CONNECTION
    # ---------------------------------------------------
    def connect(self):
        print(f"Connecting to {self.connection_string}...")
        self.master = mavutil.mavlink_connection(self.connection_string)

        heartbeat = self.master.wait_heartbeat()
        self.fcu_system = heartbeat.get_srcSystem()
        self.fcu_component = heartbeat.get_srcComponent()
        self.firmware_type = heartbeat.autopilot

        print(f"✅ Connected (SYS:{self.fcu_system} COMP:{self.fcu_component})")

        self._running = True
        threading.Thread(target=self._listener, daemon=True).start()

    # ---------------------------------------------------
    # LISTENER (Threaded)
    # ---------------------------------------------------
    def _listener(self):
        while self._running:
            msg = self.master.recv_match(blocking=True)

            if not msg:
                continue

            if msg.get_type() == "BAD_DATA":
                continue

            if msg.get_srcSystem() != self.fcu_system:
                continue

            with self._lock:

                # ---------------------------------
                # HEARTBEAT → Mode + Armed + Health
                # ---------------------------------
                if msg.get_type() == "HEARTBEAT":

                    # 1️⃣ MODE
                    mode_name = self._decode_mode(msg)
                    if mode_name != self.current_mode:
                        self.current_mode = mode_name
                        print(f"🚁 Mode → {self.current_mode}")

                    # 2️⃣ ARM STATUS
                    new_armed = bool(
                        msg.base_mode & mavlink2.MAV_MODE_FLAG_SAFETY_ARMED
                    )

                    if new_armed and not self.armed:
                        print("🚀 Armed")
                        self.vehicle_was_armed = True

                    if not new_armed and self.armed:
                        print("🛑 Disarmed")

                    self.armed = new_armed

                    # 3️⃣ MAV_STATE (Health)
                    if msg.system_status != self.system_status:
                        self.system_status = msg.system_status
                        print(f"⚠ State → {self._decode_mav_state(self.system_status)}")

                # ---------------------------------
                # EXTENDED_SYS_STATE → Flying
                # ---------------------------------
                elif msg.get_type() == "EXTENDED_SYS_STATE":

                    if msg.landed_state != self.landed_state:
                        self.landed_state = msg.landed_state

                        if self.landed_state == mavlink2.MAV_LANDED_STATE_IN_AIR:
                            print("✈️  UAV is airborne")

                        elif self.landed_state == mavlink2.MAV_LANDED_STATE_ON_GROUND:
                            print("🛬 UAV is on ground")

    def _decode_mode(self, msg):
        """
        Decode mode depending on firmware type.
        Future safe for PX4.
        """

        if self.firmware_type == mavlink2.MAV_AUTOPILOT_ARDUPILOTMEGA:
            return self.ARDUCOPTER_MODES.get(
                msg.custom_mode,
                f"UNKNOWN({msg.custom_mode})"
            )

        elif self.firmware_type == mavlink2.MAV_AUTOPILOT_PX4:
            return f"PX4_MODE({msg.custom_mode})"

        return "UNKNOWN_FIRMWARE"

    def _decode_mav_state(self, state):
        states = {
            mavlink2.MAV_STATE_UNINIT: "UNINIT",
            mavlink2.MAV_STATE_BOOT: "BOOT",
            mavlink2.MAV_STATE_CALIBRATING: "CALIBRATING",
            mavlink2.MAV_STATE_STANDBY: "STANDBY",
            mavlink2.MAV_STATE_ACTIVE: "ACTIVE",
            mavlink2.MAV_STATE_CRITICAL: "CRITICAL",
            mavlink2.MAV_STATE_EMERGENCY: "EMERGENCY",
            mavlink2.MAV_STATE_POWEROFF: "POWEROFF",
            mavlink2.MAV_STATE_FLIGHT_TERMINATION: "FLIGHT_TERMINATION",
        }

        return states.get(state, f"UNKNOWN({state})")

    def get_mode(self):
        with self._lock:
            return self.current_mode

    # ---------------------------------------------------
    # MODE CONTROL
    # ---------------------------------------------------
    def set_mode(self, mode_name="GUIDED"):
        mode_map = self.master.mode_mapping()

        if mode_name not in mode_map:
            raise ValueError(f"Mode {mode_name} not supported")

        mode_id = mode_map[mode_name]

        self.master.mav.set_mode_send(
            self.fcu_system,
            mavlink2.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id
        )

        print(f"✅ Mode command sent: {mode_name}")

    # ---------------------------------------------------
    # ARM / DISARM
    # ---------------------------------------------------
    def arm(self):
        self.master.mav.command_long_send(
            self.fcu_system,
            self.fcu_component,
            mavlink2.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1, 0, 0, 0, 0, 0, 0
        )
        print("✅ Arm command sent")

    def disarm(self):
        self.master.mav.command_long_send(
            self.fcu_system,
            self.fcu_component,
            mavlink2.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            0, 0, 0, 0, 0, 0, 0
        )
        print("🛑 Disarm command sent")

    def is_armed(self):
        with self._lock:
            return self.armed
    
    # ---------------------------------------------------
    # ATTITUDE CONTROL
    # ---------------------------------------------------
    def send_attitude_target(self, q, thrust=0.5):
        type_mask = (
            mavlink2.ATTITUDE_TARGET_TYPEMASK_BODY_ROLL_RATE_IGNORE |
            mavlink2.ATTITUDE_TARGET_TYPEMASK_BODY_PITCH_RATE_IGNORE |
            mavlink2.ATTITUDE_TARGET_TYPEMASK_BODY_YAW_RATE_IGNORE
        )

        time_boot_ms = int(self.master.time_since('HEARTBEAT') * 1000) & 0xFFFFFFFF

        self.master.mav.set_attitude_target_send(
            time_boot_ms,
            self.fcu_system,
            self.fcu_component,
            type_mask,
            q,
            0, 0, 0,
            thrust
        )

    # ---------------------------------------------------
    # POSITION TARGET (Global)
    # ---------------------------------------------------
    def send_position_target(self, lat, lon, alt):
        self.master.mav.command_long_send(
            self.fcu_system,
            self.fcu_component,
            mavlink2.MAV_CMD_NAV_WAYPOINT,
            0,
            0, 0, 0, 0,
            lat, lon, alt
        )

    # ---------------------------------------------------
    # CLEAN SHUTDOWN
    # ---------------------------------------------------
    def stop(self):
        self._running = False