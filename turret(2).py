#!/usr/bin/env python3

try:
    import cv2
except Exception:
    print("Warning: OpenCV not installed.")

import time
import threading
import atexit
import sys
import termios
import contextlib

import imutils
import RPi.GPIO as GPIO

from adafruit_motorkit import MotorKit
from adafruit_motor import stepper

MOTOR_X_REVERSED = False
MOTOR_Y_REVERSED = False

MAX_STEPS_X = 30
MAX_STEPS_Y = 15

RELAY_PIN = 22


@contextlib.contextmanager
def raw_mode(file):
    old_attrs = termios.tcgetattr(file.fileno())
    new_attrs = old_attrs[:]
    new_attrs[3] = new_attrs[3] & ~(termios.ECHO | termios.ICANON)
    try:
        termios.tcsetattr(file.fileno(), termios.TCSADRAIN, new_attrs)
        yield
    finally:
        termios.tcsetattr(file.fileno(), termios.TCSADRAIN, old_attrs)


class VideoUtils:

    @staticmethod
    def live_video(camera_port=0):
        cap = cv2.VideoCapture(camera_port)
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            cv2.imshow("Video", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        cap.release()
        cv2.destroyAllWindows()

    @staticmethod
    def get_best_contour(imgmask, threshold):
        result = cv2.findContours(
            imgmask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        if len(result) == 2:
            contours, _ = result
        else:
            _, contours, _ = result

        best_area = threshold
        best_cnt = None

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > best_area:
                best_area = area
                best_cnt = cnt

        return best_cnt


class Turret:

    def __init__(self, friendly_mode=True):
        self.friendly_mode = friendly_mode

        self.kit = MotorKit()
        self.sm_x = self.kit.stepper1
        self.sm_y = self.kit.stepper2

        self.current_x_steps = 0
        self.current_y_steps = 0

        self.x_lock = threading.Lock()
        self.y_lock = threading.Lock()

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(RELAY_PIN, GPIO.OUT)
        GPIO.output(RELAY_PIN, GPIO.LOW)

        atexit.register(self.__turn_off_motors)

    @staticmethod
    def move_forward(motor, steps, lock):
        with lock:
            for _ in range(steps):
                motor.onestep(
                    direction=stepper.FORWARD,
                    style=stepper.INTERLEAVE
                )
                time.sleep(0.01)

    @staticmethod
    def move_backward(motor, steps, lock):
        with lock:
            for _ in range(steps):
                motor.onestep(
                    direction=stepper.BACKWARD,
                    style=stepper.INTERLEAVE
                )
                time.sleep(0.01)

    @staticmethod
    def fire():
        GPIO.output(RELAY_PIN, GPIO.HIGH)
        time.sleep(1)
        GPIO.output(RELAY_PIN, GPIO.LOW)

    def __turn_off_motors(self):
        try:
            self.sm_x.release()
        except Exception:
            pass
        try:
            self.sm_y.release()
        except Exception:
            pass

    def interactive(self):
        print("Commands: a/d = pan, w/s = tilt, ENTER = fire, q = quit")

        with raw_mode(sys.stdin):
            while True:
                ch = sys.stdin.read(1)

                if not ch or ch == "q":
                    break

                if ch == "w":
                    if MOTOR_Y_REVERSED:
                        self.move_forward(self.sm_y, 5, self.y_lock)
                    else:
                        self.move_backward(self.sm_y, 5, self.y_lock)

                elif ch == "s":
                    if MOTOR_Y_REVERSED:
                        self.move_backward(self.sm_y, 5, self.y_lock)
                    else:
                        self.move_forward(self.sm_y, 5, self.y_lock)

                elif ch == "a":
                    if MOTOR_X_REVERSED:
                        self.move_backward(self.sm_x, 5, self.x_lock)
                    else:
                        self.move_forward(self.sm_x, 5, self.x_lock)

                elif ch == "d":
                    if MOTOR_X_REVERSED:
                        self.move_forward(self.sm_x, 5, self.x_lock)
                    else:
                        self.move_backward(self.sm_x, 5, self.x_lock)

                elif ch == "\n":
                    self.fire()


if __name__ == "__main__":
    t = Turret(friendly_mode=False)

    if input("Live video? (y/n)\n").lower() == "y":
        threading.Thread(
            target=VideoUtils.live_video,
            daemon=True
        ).start()

    t.interactive()
