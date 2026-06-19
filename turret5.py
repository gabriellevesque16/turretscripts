#!/usr/bin/env python3
# Automatic pan/tilt tracker - no manual controls

import time
import threading
import atexit
import cv2
import imutils
import RPi.GPIO as GPIO
from adafruit_motorkit import MotorKit
from adafruit_motor import stepper

MOTOR_X_REVERSED=False
MOTOR_Y_REVERSED=False
RELAY_PIN=22
DEADBAND_X=25
DEADBAND_Y=25
TRACKING_STEP_SIZE=2
STEP_DELAY=0.01
MOTION_AREA_THRESHOLD=5000

class VideoUtils:
    @staticmethod
    def get_best_contour(imgmask, threshold):
        result=cv2.findContours(imgmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours=result[0] if len(result)==2 else result[1]
        best=None
        best_area=threshold
        for c in contours:
            area=cv2.contourArea(c)
            if area>best_area:
                best_area=area
                best=c
        return best

    @staticmethod
    def find_motion(callback, camera_port=0, show_video=True):
        camera=cv2.VideoCapture(camera_port)
        time.sleep(0.5)
        first_frame=None

        while True:
            ok, frame=camera.read()
            if not ok:
                break

            frame=imutils.resize(frame, width=500)
            gray=cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray=cv2.GaussianBlur(gray,(21,21),0)

            if first_frame is None:
                first_frame=gray
                continue

            frame_delta=cv2.absdiff(first_frame, gray)
            thresh=cv2.threshold(frame_delta,25,255,cv2.THRESH_BINARY)[1]
            thresh=cv2.dilate(thresh,None,iterations=2)

            contour=VideoUtils.get_best_contour(thresh.copy(), MOTION_AREA_THRESHOLD)

            if contour is not None:
                callback(contour, frame)

            if show_video:
                cv2.imshow('Automatic Tracking', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        camera.release()
        cv2.destroyAllWindows()

class Turret:
    def __init__(self):
        self.kit=MotorKit()
        self.pan_motor=self.kit.stepper1
        self.tilt_motor=self.kit.stepper2
        self.pan_lock=threading.Lock()
        self.tilt_lock=threading.Lock()

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(RELAY_PIN, GPIO.OUT)
        GPIO.output(RELAY_PIN, GPIO.LOW)

        atexit.register(self.shutdown)

    def shutdown(self):
        try: self.pan_motor.release()
        except: pass
        try: self.tilt_motor.release()
        except: pass

    def _step(self,motor,direction,steps,lock):
        with lock:
            for _ in range(steps):
                motor.onestep(direction=direction, style=stepper.INTERLEAVE)
                time.sleep(STEP_DELAY)

    def pan_left(self):
        self._step(self.pan_motor,
                   stepper.BACKWARD if MOTOR_X_REVERSED else stepper.FORWARD,
                   TRACKING_STEP_SIZE,
                   self.pan_lock)

    def pan_right(self):
        self._step(self.pan_motor,
                   stepper.FORWARD if MOTOR_X_REVERSED else stepper.BACKWARD,
                   TRACKING_STEP_SIZE,
                   self.pan_lock)

    def tilt_up(self):
        self._step(self.tilt_motor,
                   stepper.FORWARD if MOTOR_Y_REVERSED else stepper.BACKWARD,
                   TRACKING_STEP_SIZE,
                   self.tilt_lock)

    def tilt_down(self):
        self._step(self.tilt_motor,
                   stepper.BACKWARD if MOTOR_Y_REVERSED else stepper.FORWARD,
                   TRACKING_STEP_SIZE,
                   self.tilt_lock)

    def track_target(self, contour, frame):
        frame_h, frame_w = frame.shape[:2]
        x,y,w,h = cv2.boundingRect(contour)

        error_x = (x + w/2) - (frame_w/2)
        error_y = (y + h/2) - (frame_h/2)

        if error_x < -DEADBAND_X:
            self.pan_left()
        elif error_x > DEADBAND_X:
            self.pan_right()

        if error_y < -DEADBAND_Y:
            self.tilt_up()
        elif error_y > DEADBAND_Y:
            self.tilt_down()

    def start_tracking(self):
        VideoUtils.find_motion(self.track_target, show_video=True)

if __name__ == '__main__':
    turret = Turret()
    print('Starting automatic motion tracking...')
    print("Press 'q' in the video window to quit.")
    turret.start_tracking()
