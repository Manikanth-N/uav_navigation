# controllers/landing.py
class LandingController:

    def __init__(self, uav):
        self.uav = uav

    def update(self, altitude):

        if altitude < 10 and self.uav.is_flying():
            self.uav.gimbal.set_pitch(-90)

        if not self.uav.is_armed():
            print("Landing complete")