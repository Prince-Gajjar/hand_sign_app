import cv2  # pyre-ignore
import mediapipe as mp  # pyre-ignore
import pyttsx3  # pyre-ignore
import supabase  # pyre-ignore
import sklearn  # pyre-ignore
import numpy as np  # pyre-ignore
print("All imports successful")

try:
    engine = pyttsx3.init()
    print("TTS initialized")
except Exception as e:
    print(f"TTS failed: {e}")

try:
    hands = mp.solutions.hands.Hands()
    print("Mediapipe initialized")
except Exception as e:
    print(f"Mediapipe failed: {e}")

try:
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    print(f"Camera check: {ret}")
    cap.release()
except Exception as e:
    print(f"Camera failed: {e}")
