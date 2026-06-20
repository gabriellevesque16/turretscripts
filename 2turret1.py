#!/usr/bin/env python3
"""PiFace converted from servos to Adafruit MotorKit steppers."""

import time
import cv2
from adafruit_motorkit import MotorKit
from adafruit_motor import stepper

PAN_LIMIT = 400
TILT_LIMIT = 250
STEP_DELAY = 0.005

webcam = cv2.VideoCapture(0)
webcam.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
webcam.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

frontalface = cv2.CascadeClassifier('haarcascade_frontalface_alt2.xml')
profileface = cv2.CascadeClassifier('haarcascade_profileface.xml')

kit = MotorKit()
pan_motor = kit.stepper1
tilt_motor = kit.stepper2

pan_position = 0
tilt_position = 0
lastface = 0

def step_motor(motor, direction, steps):
    for _ in range(int(steps)):
        motor.onestep(direction=direction, style=stepper.INTERLEAVE)
        time.sleep(STEP_DELAY)

def CamRight(distance, speed):
    global pan_position
    if pan_position < PAN_LIMIT:
        step_motor(pan_motor, stepper.FORWARD, distance)
        pan_position += distance

def CamLeft(distance, speed):
    global pan_position
    if pan_position > -PAN_LIMIT:
        step_motor(pan_motor, stepper.BACKWARD, distance)
        pan_position -= distance

def CamDown(distance, speed):
    global tilt_position
    if tilt_position < TILT_LIMIT:
        step_motor(tilt_motor, stepper.FORWARD, distance)
        tilt_position += distance

def CamUp(distance, speed):
    global tilt_position
    if tilt_position > -TILT_LIMIT:
        step_motor(tilt_motor, stepper.BACKWARD, distance)
        tilt_position -= distance

while True:
    faceFound = False
    face = [0,0,0,0]

    frame = webcam.read()[1]
    if frame is None:
        continue

    faces = frontalface.detectMultiScale(frame, 1.3, 4)

    if len(faces):
        face = faces[0]
        faceFound = True

    if not faceFound:
        faces = profileface.detectMultiScale(frame, 1.3, 4)
        if len(faces):
            face = faces[0]
            faceFound = True

    if faceFound:
        x,y,w,h = face
        cx = x + w/2
        cy = y + h/2

        print(f'{cx},{cy}')

        if cx > 180: CamLeft(5,1)
        if cx > 190: CamLeft(7,2)
        if cx > 200: CamLeft(9,3)

        if cx < 140: CamRight(5,1)
        if cx < 130: CamRight(7,2)
        if cx < 120: CamRight(9,3)

        if cy > 140: CamDown(5,1)
        if cy > 150: CamDown(7,2)
        if cy > 160: CamDown(9,3)

        if cy < 100: CamUp(5,1)
        if cy < 90: CamUp(7,2)
        if cy < 80: CamUp(9,3)
