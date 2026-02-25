# examples/test.py

from uav_sdk.core.vehicle import UAV
import time

uav = UAV("tcp:127.0.0.1:5763")
uav.connect()


while True:

    time.sleep(1)