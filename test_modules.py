import os
import cv2  # pyre-ignore
import mediapipe as mp  # pyre-ignore
from camera_module import CameraFeed  # pyre-ignore
from gesture_detector import GestureDetector  # pyre-ignore
from speech_engine import SpeechEngine  # pyre-ignore

print("Initializing CameraFeed...")
try:
    camera = CameraFeed()
    print("CameraFeed initialized")
    ret, frame = camera.get_frame()
    print(f"Frame capture test: {ret}")
    camera.release()
except Exception as e:
    print(f"CameraFeed failed: {e}")

print("\nInitializing GestureDetector...")
try:
    detector = GestureDetector()
    print("GestureDetector initialized")
except Exception as e:
    print(f"GestureDetector failed: {e}")

print("\nInitializing SpeechEngine...")
try:
    speech = SpeechEngine()
    print("SpeechEngine initialized")
except Exception as e:
    print(f"SpeechEngine failed: {e}")
