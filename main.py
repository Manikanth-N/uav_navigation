from uav_sdk.core.vehicle import UAV
from pymavlink.dialects.v20 import common as mavlink2


def main():
    connection_string = 'tcp:127.0.0.1:5763'
    uav = UAV(connection_string)
    uav.connect()
    uav.set_mode('GUIDED')
    uav.arm()

    while True:
        pass
        

if __name__ == "__main__":
    main()
