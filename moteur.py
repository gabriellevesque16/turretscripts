import threading
import atexit
import board
import RPi.GPIO as GPIO

from adafruit_motorkit import MotorKit
from adafruit_motor import stepper as STEPPER

#setup moteurs#############################################################################
kit = MotorKit(i2c=board.I2C())

st1 = threading.Thread()
st2 = threading.Thread()

#pin du gun
RELAY_PIN = 22

def StopMoteurs():
    kit.stepper1.release()
    kit.stepper2.release()

atexit.register(StopMoteurs)

def mov_horizontal(numsteps, direction, style):
  for _ in range(numsteps):
    kit.stepper1.onestep(direction, style)

#exemple
#mov_horizontal(2, STEPPER.FORWARD ou STEPPER.BACKWARD, STEPPER.SINGLE ou STEPPER.DOUBLE etc)

def mov_vertical(numsteps, direction, style):
  for _ in range(numsteps):
    kit.stepper2.onestep(direction, style)



        