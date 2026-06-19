#!/usr/bin/env python3

# Pan/Tilt tracking turret using MotorKit
# Generated from requested architecture.

try:
    import cv2
except ImportError:
    print('OpenCV not installed.')
    raise

import time, threading, atexit, sys, termios, contextlib
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

@contextlib.contextmanager
def raw_mode(file):
    old=termios.tcgetattr(file.fileno())
    new=old[:]
    new[3] &= ~(termios.ECHO | termios.ICANON)
    try:
        termios.tcsetattr(file.fileno(), termios.TCSADRAIN, new)
        yield
    finally:
        termios.tcsetattr(file.fileno(), termios.TCSADRAIN, old)

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
    def find_motion(callback, camera_port=0, show_video=False):
        camera=cv2.VideoCapture(camera_port)
        time.sleep(0.5)
        first_frame=None
        while True:
            ok, frame=camera.read()
            if not ok:
                break
            frame=imutils.resize(frame,width=500)
            gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
            gray=cv2.GaussianBlur(gray,(21,21),0)
            if first_frame is None:
                first_frame=gray
                continue
            frame_delta=cv2.absdiff(first_frame,gray)
            thresh=cv2.threshold(frame_delta,25,255,cv2.THRESH_BINARY)[1]
            thresh=cv2.dilate(thresh,None,iterations=2)
            contour=VideoUtils.get_best_contour(thresh.copy(), MOTION_AREA_THRESHOLD)
            if contour is not None:
                callback(contour, frame)
            if show_video:
                cv2.imshow('Tracking', frame)
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
        try:self.pan_motor.release()
        except: pass
        try:self.tilt_motor.release()
        except: pass

    def _step_motor(self,motor,direction,steps,lock):
        with lock:
            for _ in range(steps):
                motor.onestep(direction=direction, style=stepper.INTERLEAVE)
                time.sleep(STEP_DELAY)

    def pan_left(self):
        self._step_motor(self.pan_motor, stepper.BACKWARD if MOTOR_X_REVERSED else stepper.FORWARD, TRACKING_STEP_SIZE, self.pan_lock)
    def pan_right(self):
        self._step_motor(self.pan_motor, stepper.FORWARD if MOTOR_X_REVERSED else stepper.BACKWARD, TRACKING_STEP_SIZE, self.pan_lock)
    def tilt_up(self):
        self._step_motor(self.tilt_motor, stepper.FORWARD if MOTOR_Y_REVERSED else stepper.BACKWARD, TRACKING_STEP_SIZE, self.tilt_lock)
    def tilt_down(self):
        self._step_motor(self.tilt_motor, stepper.BACKWARD if MOTOR_Y_REVERSED else stepper.FORWARD, TRACKING_STEP_SIZE, self.tilt_lock)

    def calibrate(self):
        print('Calibration mode: a/d pan, w/s tilt, ENTER finish')
        with raw_mode(sys.stdin):
            while True:
                ch=sys.stdin.read(1)
                if ch=='a': self.pan_left()
                elif ch=='d': self.pan_right()
                elif ch=='w': self.tilt_up()
                elif ch=='s': self.tilt_down()
                elif ch=='\n': break

    def track_target(self, contour, frame):
        h,w=frame.shape[:2]
        x,y,cw,ch=cv2.boundingRect(contour)
        error_x=(x+cw/2)-(w/2)
        error_y=(y+ch/2)-(h/2)
        if error_x < -DEADBAND_X: self.pan_left()
        elif error_x > DEADBAND_X: self.pan_right()
        if error_y < -DEADBAND_Y: self.tilt_up()
        elif error_y > DEADBAND_Y: self.tilt_down()

    def motion_detection(self, show_video=True):
        VideoUtils.find_motion(self.track_target, show_video=show_video)

if __name__=='__main__':
    turret=Turret()
    turret.calibrate()
    turret.motion_detection(True)
