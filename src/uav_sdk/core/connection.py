# src/uav_sdk/core/connection.py

import threading
from pymavlink import mavutil
from pymavlink.dialects.v20 import common as mavlink2
from .dispatcher import Dispatcher


class MAVLinkConnection:

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

    def __init__(self, connection_string, state):
        self.connection_string = connection_string
        self.state = state
        self.master = None
        self.system_id = None
        self.component_id = None
        self._running = False
        self.dispatcher = Dispatcher()
        self.param_cache = {}

    def connect(self):
        print(f"Connecting to {self.connection_string}...")
        self.master = mavutil.mavlink_connection(self.connection_string)
        self.master.wait_heartbeat()

        self.system_id = self.master.target_system
        self.component_id = self.master.target_component

        print(f"✅ Connected (SYS:{self.system_id})")

        self._running = True
        threading.Thread(target=self._listener, daemon=True).start()

    def _listener(self):
        while self._running:

            msg = self.master.recv_match(blocking=True)

            if not msg:
                continue

            # Dispatch ALL messages
            self.dispatcher.dispatch(msg)

            msg_type = msg.get_type()

            # -------------------------
            # PARAMETER CACHE
            # -------------------------
            if msg_type == "PARAM_VALUE":
                param_id = msg.param_id
                if isinstance(param_id, bytes):
                    param_id = param_id.decode()
                param_id = param_id.strip('\x00')
                self.param_cache[param_id] = msg.param_value

            # -------------------------
            # HEARTBEAT PROCESSING
            # -------------------------
            if msg_type == "HEARTBEAT":

                if msg.get_srcSystem() != self.system_id:
                    continue

                armed = bool(
                    msg.base_mode & mavlink2.MAV_MODE_FLAG_SAFETY_ARMED
                )
                
                
                # Update state
                self.state.update("armed", armed)

                mode_number = msg.custom_mode
                mode_name = self.ARDUCOPTER_MODES.get(mode_number, "UNKNOWN")
                self.state.update("mode", mode_name)

                flying = msg.system_status == mavlink2.MAV_STATE_ACTIVE
                self.state.update("flying", flying)