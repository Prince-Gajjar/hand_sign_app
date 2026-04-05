import cv2
import traceback
from gesture_detector import GestureDetector

det = GestureDetector()
frame = cv2.imread('asl_dataset/train/A/A_01632.jpg') # ensure image exists
if frame is None:
    frame = cv2.imread('asl_dataset/train/B/B_01632.jpg')
if frame is not None:
    _, gesture, conf = det.detect(frame)
    if hasattr(det, 'last_landmarks') and det.last_landmarks:
        print("Landmarks found")
        try:
            for hl in det.last_landmarks:
                det.mp_draw.draw_landmarks(
                    frame,
                    hl,
                    det.mp_hands.HAND_CONNECTIONS,
                    det.mp_draw.DrawingSpec(color=(0, 150, 136), thickness=2, circle_radius=2),
                    det.mp_draw.DrawingSpec(color=(255, 255, 255), thickness=1, circle_radius=1)
                )
            print("DRAW_SUCCESS")
        except Exception as e:
            traceback.print_exc()
    else:
        print("No landmarks detected")
else:
    print("No image")
