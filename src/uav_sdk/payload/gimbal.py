# payload/gimbal.py
from pymavlink.dialects.v20 import common as mavlink2

class Gimbal:

    def __init__(self, connection):
        self.conn = connection

    def set_pitch(self, pitch_deg):
        self.conn.master.mav.command_long_send(
            self.conn.system_id,
            self.conn.component_id,
            mavlink2.MAV_CMD_DO_MOUNT_CONTROL,
            0,
            pitch_deg, 0, 0,
            0, 0, 0,
            mavlink2.MAV_MOUNT_MODE_MAVLINK_TARGETING
        )

    def center(self):
        self.set_pitch(0)