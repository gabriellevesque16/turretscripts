#!/usr/bin/env python3
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

MOTOR_X_REVERSED = False
MOTOR_Y_REVERSED = False

MAX_STEPS_X = 30
MAX_STEPS_Y = 15

RELAY_PIN = 22


@contextlib.contextmanager
def raw_mode(file):
    old_attrs = termios.tcgetattr(file.fileno())
    new_attrs = old_attrs[:]
    new_attrs[3] &= ~(termios.ECHO | termios.ICANON)
    try:
        termios.tcsetattr(file.fileno(), termios.TCSADRAIN, new_attrs)
        yield
    finally:
        termios.tcsetattr(file.fileno(), termios.TCSADRAIN, old_attrs)


class VideoUtils:

    @staticmethod
    def live_video(camera_port=0):
        video_capture = cv2.VideoCapture(camera_port)

        while True:
            ret, frame = video_capture.read()
            if not ret:
                break

            cv2.imshow("Video", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        video_capture.release()
        cv2.destroyAllWindows()

    @staticmethod
    def find_motion(callback, camera_port=0, show_video=False):
        camera = cv2.VideoCapture(camera_port)
        time.sleep(0.25)

        first_frame = None
        temp_frame = None
        count = 0

        while True:
            grabbed, frame = camera.read()

            if not grabbed:
                break

            frame = imutils.resize(frame, width=500)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            if first_frame is None:
                print("Waiting for video to adjust...")

                if temp_frame is None:
                    temp_frame = gray
                    continue

                delta = cv2.absdiff(temp_frame, gray)
                temp_frame = gray

                tst = cv2.threshold(delta, 5, 255, cv2.THRESH_BINARY)[1]
                tst = cv2.dilate(tst, None, iterations=2)

                if count > 30:
                    print("Done.\nWaiting for motion.")
                    if cv2.countNonZero(tst) == 0:
                        first_frame = gray
                    else:
                        continue
                else:
                    count += 1
                    continue

            frame_delta = cv2.absdiff(first_frame, gray)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)

            c = VideoUtils.get_best_contour(thresh.copy(), 5000)

            if c is not None:
                x, y, w, h = cv2.boundingRect(c)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                callback(c, frame)

            if show_video:
                cv2.imshow("Security Feed", frame)
                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    break

        camera.release()
        cv2.destroyAllWindows()

    @staticmethod
    def get_best_contour(imgmask, threshold):
        result = cv2.findContours(imgmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

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

    def calibrate(self):
        print("Please calibrate the tilt of the gun so that it is level. Commands: (w) moves up, (s) moves down. Press (enter) to finish.\n")
        self.__calibrate_y_axis()

        print("Please calibrate the yaw of the gun so that it aligns with the camera. Commands: (a) moves left, (d) moves right. Press (enter) to finish.\n")
        self.__calibrate_x_axis()

        print("Calibration finished.")

    def __calibrate_x_axis(self):
        with raw_mode(sys.stdin):
            while True:
                ch = sys.stdin.read(1)

                if not ch:
                    break
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
                    break

    def __calibrate_y_axis(self):
        with raw_mode(sys.stdin):
            while True:
                ch = sys.stdin.read(1)

                if not ch:
                    break
                elif ch == "w":
                    if MOTOR_Y_REVERSED:
                        self.move_forward(self.sm_y, 5, self.y_lock)
                    else:
                        self.move_backward(self.sm_y, 5, self.y_lock)
                elif ch == "s":
                    if MOTOR_Y_REVERSED:
                        self.move_backward(self.sm_y, 5, self.y_lock)
                    else:
                        self.move_forward(self.sm_y, 5, self.y_lock)
                elif ch == "\n":
                    break

    def motion_detection(self, show_video=False):
        VideoUtils.find_motion(self.__move_axis, show_video=show_video)

    def __move_axis(self, contour, frame):
        v_h, v_w = frame.shape[:2]
        x, y, w, h = cv2.boundingRect(contour)

        target_steps_x = (2 * MAX_STEPS_X * (x + (w / 2.0)) / v_w) - MAX_STEPS_X
        target_steps_y = (2 * MAX_STEPS_Y * (y + (h / 2.0)) / v_h) - MAX_STEPS_Y

        print(f"x: {target_steps_x}, y: {target_steps_y}")
        print(f"current x: {self.current_x_steps}, current y: {self.current_y_steps}")

        t_x = threading.Thread()
        t_y = threading.Thread()
        t_fire = threading.Thread()

        if (target_steps_x - self.current_x_steps) > 0:
            self.current_x_steps += 1
            t_x = threading.Thread(target=self.move_forward if MOTOR_X_REVERSED else self.move_backward,
                                   args=(self.sm_x, 2, self.x_lock))
        elif (target_steps_x - self.current_x_steps) < 0:
            self.current_x_steps -= 1
            t_x = threading.Thread(target=self.move_backward if MOTOR_X_REVERSED else self.move_forward,
                                   args=(self.sm_x, 2, self.x_lock))

        if (target_steps_y - self.current_y_steps) > 0:
            self.current_y_steps += 1
            t_y = threading.Thread(target=self.move_backward if MOTOR_Y_REVERSED else self.move_forward,
                                   args=(self.sm_y, 2, self.y_lock))
        elif (target_steps_y - self.current_y_steps) < 0:
            self.current_y_steps -= 1
            t_y = threading.Thread(target=self.move_forward if MOTOR_Y_REVERSED else self.move_backward,
                                   args=(self.sm_y, 2, self.y_lock))

        if not self.friendly_mode:
            if abs(target_steps_y - self.current_y_steps) <= 2 and abs(target_steps_x - self.current_x_steps) <= 2:
                t_fire = threading.Thread(target=Turret.fire)

        t_x.start(); t_y.start(); t_fire.start()
        t_x.join(); t_y.join(); t_fire.join()

    def interactive(self):
        self.move_forward(self.sm_x, 1, self.x_lock)
        self.move_forward(self.sm_y, 1, self.y_lock)

        print("Commands: Pivot with (a) and (d). Tilt with (w) and (s). Exit with (q)")

        with raw_mode(sys.stdin):
            while True:
                ch = sys.stdin.read(1)

                if not ch or ch == "q":
                    break

                if ch == "w":
                    (self.move_forward if MOTOR_Y_REVERSED else self.move_backward)(self.sm_y, 5, self.y_lock)
                elif ch == "s":
                    (self.move_backward if MOTOR_Y_REVERSED else self.move_forward)(self.sm_y, 5, self.y_lock)
                elif ch == "a":
                    (self.move_backward if MOTOR_X_REVERSED else self.move_forward)(self.sm_x, 5, self.x_lock)
                elif ch == "d":
                    (self.move_forward if MOTOR_X_REVERSED else self.move_backward)(self.sm_x, 5, self.x_lock)
                elif ch == "\n":
                    Turret.fire()

    @staticmethod
    def fire():
        GPIO.output(RELAY_PIN, GPIO.HIGH)
        time.sleep(1)
        GPIO.output(RELAY_PIN, GPIO.LOW)

    @staticmethod
    def move_forward(motor, steps, lock):
        with lock:
            for _ in range(steps):
                motor.onestep(direction=stepper.FORWARD, style=stepper.INTERLEAVE)
                time.sleep(0.01)

    @staticmethod
    def move_backward(motor, steps, lock):
        with lock:
            for _ in range(steps):
                motor.onestep(direction=stepper.BACKWARD, style=stepper.INTERLEAVE)
                time.sleep(0.01)

    def __turn_off_motors(self):
        try:
            self.sm_x.release()
        except Exception:
            pass
        try:
            self.sm_y.release()
        except Exception:
            pass


if __name__ == "__main__":
    t = Turret(friendly_mode=False)

    user_input = input("Choose an input mode: (1) Motion Detection, (2) Interactive\n")

    if user_input == "1":
        t.calibrate()
        if input("Live video? (y, n)\n").lower() == "y":
            t.motion_detection(show_video=True)
        else:
            t.motion_detection()
    elif user_input == "2":
        if input("Live video? (y, n)\n").lower() == "y":
            threading.Thread(target=VideoUtils.live_video, daemon=True).start()
        t.interactive()
    else:
        print("Unknown input mode. Please choose a number (1) or (2)")
