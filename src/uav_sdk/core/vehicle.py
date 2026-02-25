# src/uav_sdk/core/vehicle.py

from pymavlink.dialects.v20 import common as mavlink2
from .state import UAVState
from .connection import MAVLinkConnection


class UAV:

    def __init__(self, connection_string):
        self.state = UAVState()
        self.connection = MAVLinkConnection(connection_string, self.state)

    def connect(self):
        self.connection.connect()

         # Register callbacks
        self.on("armed", self.on_arm)
        self.on("mode", self.on_mode)
        self.on("flying", self.on_flying)

    # ---- Control ----

    def arm(self):
        self.connection.master.mav.command_long_send(
            self.connection.system_id,
            self.connection.component_id,
            mavlink2.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1, 0, 0, 0, 0, 0, 0
        )

    def disarm(self):
        self.connection.master.mav.command_long_send(
            self.connection.system_id,
            self.connection.component_id,
            mavlink2.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            0, 0, 0, 0, 0, 0, 0
        )

    def set_mode(self, mode_name):
        mode_id = self.connection.master.mode_mapping()[mode_name]

        self.connection.master.mav.set_mode_send(
            self.connection.system_id,
            mavlink2.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id
        )

    # ---- Callback registration ----

    def on(self, key, callback):
        self.state.on(key, callback)

    # ---- State access ----

    def is_armed(self):
        return self.state.get("armed")

    def get_mode(self):
        return self.state.get("mode")

    def is_flying(self):
        return self.state.get("flying")

    
    # ------------------------
    # Terminal Attention Prints
    # ------------------------

    COLORS = {
        "red": "\033[91m",
        "green": "\033[92m",
        "cyan": "\033[96m",
        "yellow": "\033[93m",
        "bold": "\033[1m",
        "end": "\033[0m"
    }

    def on_arm(self, state):
        color = self.COLORS["green"] if state else self.COLORS["red"]

        print(
            f"\n{self.COLORS['bold']}{color}{'='*50}"
        )
        print(f"   ARMED STATUS: {state}")
        print(
            f"{'='*50}{self.COLORS['end']}\n"
        )

    def on_mode(self, mode):
        print(
            f"{self.COLORS['bold']}{self.COLORS['cyan']}"
            f">>> MODE: {mode}"
            f"{self.COLORS['end']}"
        )

    def on_flying(self, state):
        color = self.COLORS["green"] if state else self.COLORS["yellow"]

        print(
            f"{self.COLORS['bold']}{color}"
            f">>> FLYING: {state}"
            f"{self.COLORS['end']}"
        )
   