try:
    import cv2
except Exception:
    print("Warning: OpenCV not installed. To use motion detection, make sure you've properly configured OpenCV.")

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

kit = MotorKit(i2c=board.I2C())

for i in range(500):
    kit.stepper1.onestep()
    time.sleep(0.01)

for i in range(500):
    kit.stepper2.onestep()
    time.sleep(0.01)

kit.stepper1.release()
kit.stepper2.release()
