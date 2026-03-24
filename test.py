# examples/test_keyboard_gimbal.py

from uav_sdk.core.vehicle import UAV
import time
import curses
import math

uav = UAV("tcp:127.0.0.1:5763")
uav.connect()

uav.gimbal.start()       # does everything internally

# uav.gimbal.move_right(5)
# uav.gimbal.move_down(10)
# uav.gimbal.center()

while True:
    
    if uav.get_mode() == "LAND":
        uav.gimbal.set_absolute(roll=0, pitch=-90, yaw=0)
    else:
        uav.gimbal.set_absolute(roll=0, pitch=0, yaw=0)
    time.sleep(0.1)


