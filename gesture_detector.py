import cv2  # pyre-ignore # type: ignore
import os
import pickle
import numpy as np  # pyre-ignore # type: ignore
import typing
import warnings
import logging
import math
from typing import cast, Any, List, Optional, Tuple
from collections import deque, Counter

# Suppress noisy logs before heavy imports
warnings.filterwarnings("ignore", message="SymbolDatabase.GetPrototype")
warnings.filterwarnings("ignore", category=UserWarning, module="google.protobuf")
logging.getLogger("absl").setLevel(logging.WARNING)

# Static analysis guards - wrapped to prevent IDE misfires
try:
    import sklearn  # pyre-ignore # type: ignore
    from sklearn.ensemble import RandomForestClassifier  # pyre-ignore # type: ignore
except (ImportError, Exception):
    pass

try:
    import mediapipe as mp  # pyre-ignore # type: ignore
    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils
    print("DEBUG: Mediapipe solutions loaded successfully")
except Exception as e:
    mp = None
    mp_hands = None
    mp_draw = None
    print(f"CRITICAL ERROR: Mediapipe failed to load: {e}")
    import traceback
    traceback.print_exc()

class GestureDetector:
    """Uses a combination of MediaPipe landmarks and a trained Random Forest model for ASL detection."""
    def __init__(self, model_path: str = "models/gesture_model.pkl"):
        # Explicitly typed for IDE
        self.cooldown: int = 0
        # Smaller buffer = faster response (was 5 → now 3)
        self.buffer_size = 5 # Increased slightly for stability
        self.detection_buffer: deque = deque(maxlen=self.buffer_size)
        self.custom_gestures: dict = {}
        self.last_features: List[float] = []
        self.last_landmarks: Any = None
        self.model: Any = None
        self.labels: Any = None

        self.mp_hands = mp_hands
        if mp is not None and mp_hands is not None:
            self.hands = mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
                model_complexity=0  # 0 for Lite (fastest)
            )
        else:
            self.hands = None

        self.mp_draw = mp_draw

        if os.path.exists(model_path):
            try:
                with open(model_path, 'rb') as f:
                    model_data = pickle.load(f)
                    if isinstance(model_data, dict):
                        self.model = model_data.get('model')
                        self.labels = model_data.get('labels')
                    else:
                        # Legacy: raw model object
                        self.model = model_data
                print(f"Loaded gesture model from {model_path}")
            except Exception as e:
                print(f"Error loading model: {e}")

    def _calculate_angle(self, a, b, c) -> float:
        """Calculates the angle (in degrees) at point B given points A, B, C."""
        try:
            a = np.array(a)
            b = np.array(b)
            c = np.array(c)
            ba = a - b
            bc = c - b
            cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
            angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
            return float(np.degrees(angle))
        except Exception:
            return 0.0

    def _get_finger_angles(self, landmarks) -> List[float]:
        """Extracts key angles from finger joints for rotation-invariant detection."""
        try:
            lms = [[lm.x, lm.y, lm.z] for lm in landmarks.landmark]
            angles = []
            # Indices for PIP-MCP-Wrist and TIP-PIP-MCP for each finger
            # 0: Wrist, 1-4: Thumb, 5-8: Index, 9-12: Middle, 13-16: Ring, 17-20: Pinky
            finger_indices = [(5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20)] # TIP-PIP-MCPish
            for i, j, k in finger_indices:
                angles.append(self._calculate_angle(lms[i], lms[j], lms[k]))

            # Thumb angle (Wrist-MCP-TIP)
            angles.append(self._calculate_angle(lms[0], lms[2], lms[4]))
            return angles
        except Exception:
            return [0.0] * 5

    def _get_normalized_landmarks(self, landmarks) -> List[float]:
        """Centers landmarks at wrist and scales by hand size for position-invariant detection utilizing NumPy."""
        try:
            # Vectorized for maximum performance
            lm_array = np.array([[lm.x, lm.y, lm.z] for lm in landmarks.landmark], dtype=np.float32)

            # 1. Centering (Relative to Wrist - Landmark 0)
            wrist = lm_array[0]
            centered = lm_array - wrist

            # Flatten
            flattened = centered.flatten()

            # 2. Scaling (Position Invariant)
            max_val = float(np.max(np.abs(flattened)))
            if max_val > 0:
                return (flattened / max_val).tolist()
            return flattened.tolist()
        except Exception as e:
            print(f"Landmark normalisation error: {e}")
            return []

    def detect(self, frame):
        """Analyzes frame image for sign-language compatible hand mapping patterns."""
        try:
            return self._detect_inner(frame)
        except Exception as e:
            print(f"GestureDetector.detect() recovered from error: {e}")
            return frame, None, 0.0

    def _detect_inner(self, frame):
        """Core detection logic — separated for clean crash protection."""
        hands_obj = self.hands
        if hands_obj is None:
            return frame, None, 0.0

        # Performance Optimization: Resize frame to balanced resolution
        proc_w, proc_h = 320, 240
        try:
            small_frame = cv2.resize(frame, (proc_w, proc_h), interpolation=cv2.INTER_LINEAR)
        except Exception:
            return frame, None, 0.0

        rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
        rgb_frame.flags.writeable = False
        result = hands_obj.process(rgb_frame)
        rgb_frame.flags.writeable = True

        raw_gesture: Optional[str] = None
        current_confidence: float = 0.0

        if self.cooldown > 0:
            self.cooldown -= 1

        self.last_landmarks = result.multi_hand_landmarks

        if result.multi_hand_landmarks:
            num_hands: int = len(result.multi_hand_landmarks)
            hands_up: int = 0

            for hand_landmarks in result.multi_hand_landmarks:
                if self.mp_draw is not None:
                    try:
                        self.mp_draw.draw_landmarks(
                            frame,
                            hand_landmarks,
                            self.mp_hands.HAND_CONNECTIONS,
                            self.mp_draw.DrawingSpec(color=(0, 150, 136), thickness=2, circle_radius=2),
                            self.mp_draw.DrawingSpec(color=(255, 255, 255), thickness=1, circle_radius=1)
                        )
                    except Exception:
                        pass

                try:
                    if self._are_fingers_open(hand_landmarks) >= 4:
                        hands_up += 1
                except Exception:
                    pass

            # 1. EMERGENCY check (Independent of ML for reliability)
            if num_hands == 2 and hands_up == 2 and self.cooldown == 0:
                self.cooldown = 40
                return frame, "EMERGENCY", 0.95

            # 2. Gesture Logic
            elif self.cooldown == 0 and num_hands > 0:
                primary_hand = result.multi_hand_landmarks[0]
                normalized_features = self._get_normalized_landmarks(primary_hand)

                if not normalized_features:
                    self.detection_buffer.append("None")
                    return frame, None, 0.0

                self.last_features = normalized_features

                # --- STEP A: Custom Gestures ---
                matched_custom = False
                if self.custom_gestures:
                    try:
                        feat_arr = np.array(normalized_features, dtype=np.float32)
                        best_dist = float('inf')
                        best_match = None
                        for custom_phrase, custom_feats in self.custom_gestures.items():
                            diff = feat_arr - np.array(custom_feats, dtype=np.float32)
                            dist = float(np.sqrt(np.dot(diff, diff)))
                            if dist < best_dist:
                                best_dist = dist
                                best_match = custom_phrase
                        if best_match is not None and best_dist < 0.4:
                            raw_gesture = best_match
                            current_confidence = float(max(0.0, 1.0 - best_dist))
                            matched_custom = True
                    except Exception:
                        pass

                # --- STEP B: ML Model ---
                if not matched_custom and self.model is not None:
                    try:
                        features_arr = np.array(normalized_features, dtype=np.float32).reshape(1, -1)
                        if hasattr(self.model, 'predict_proba'):
                            probs = self.model.predict_proba(features_arr)
                            prob_max = float(np.max(probs))
                            if prob_max > 0.5:
                                raw_gesture = str(self.model.predict(features_arr)[0])
                                current_confidence = prob_max
                        else:
                            raw_gesture = str(self.model.predict(features_arr)[0])
                            current_confidence = 0.8
                    except Exception:
                        pass

                # --- STEP C: Improved Heuristics (Fallback) ---
                if not matched_custom and raw_gesture is None:
                    try:
                        angles = self._get_finger_angles(primary_hand)
                        fingers_open = self._are_fingers_open(primary_hand)

                        if fingers_open >= 4:
                            raw_gesture = "HELLO"
                            current_confidence = 0.6
                        elif self._is_thumb_up(primary_hand):
                            raw_gesture = "YES"
                            current_confidence = 0.6
                        elif self._is_fist(primary_hand):
                            raw_gesture = "NO"
                            current_confidence = 0.5
                    except Exception:
                        pass

        # Smoothing
        self.detection_buffer.append(raw_gesture if raw_gesture else "None")
        counts = Counter(self.detection_buffer)
        stable_gesture, freq = counts.most_common(1)[0]

        final_gesture: Optional[str] = None
        if stable_gesture != "None" and freq >= int(self.buffer_size * 0.7):
            final_gesture = stable_gesture
            if self.cooldown == 0:
                self.cooldown = 15

        return frame, final_gesture, float(current_confidence)

    def _are_fingers_open(self, landmarks) -> int:
        """Improved finger counting using both TIP position and joint angles."""
        count: int = 0
        tips = [8, 12, 16, 20]
        pips = [6, 10, 14, 18]
        try:
            for tip, pip in zip(tips, pips):
                # Basic check: Tip is above PIP joint
                if float(landmarks.landmark[tip].y) < float(landmarks.landmark[pip].y):
                    count += 1
        except Exception:
            pass
        return count

    def _is_thumb_up(self, landmarks) -> bool:
        try:
            # Thumb TIP (4) should be higher than thumb MCP (2) and all other fingers down
            thumb_tip = landmarks.landmark[4]
            thumb_mcp = landmarks.landmark[2]
            fingers_open = self._are_fingers_open(landmarks)

            # Thumb is "open" and other fingers are closed
            is_pointing_up = thumb_tip.y < thumb_mcp.y
            return fingers_open == 0 and is_pointing_up
        except Exception:
            return False

    def _is_fist(self, landmarks) -> bool:
        try:
            return self._are_fingers_open(landmarks) == 0 and landmarks.landmark[4].y > landmarks.landmark[3].y
        except Exception:
            return False
