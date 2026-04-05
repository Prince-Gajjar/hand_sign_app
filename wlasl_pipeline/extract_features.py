import os
import cv2
import json
import numpy as np
import mediapipe as mp

# Configure Paths from the WLASL dataset downloaded
WLASL_JSON_PATH = "WLASL_v0.3.json" 
VIDEOS_DIR = "videos/"
OUTPUT_FEATURES = "wlasl_features.npy"
OUTPUT_LABELS = "wlasl_labels.npy"

# We only care about these 6 classes for the MVP
TARGET_CLASSES = ["hello", "thank you", "yes", "no", "help", "please"]
SEQUENCE_LENGTH = 30 # Number of frames per sequence

def extract_wlasl_features():
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(static_image_mode=False, max_num_hands=2, min_detection_confidence=0.5)
    
    with open(WLASL_JSON_PATH, 'r') as f:
        data = json.load(f)

    X, Y = [], []

    for entry in data:
        gloss = entry['gloss'].lower()
        if gloss not in TARGET_CLASSES:
            continue

        for instance in entry['instances']:
            video_id = instance['video_id']
            video_path = os.path.join(VIDEOS_DIR, f"{video_id}.mp4")
            
            if not os.path.exists(video_path):
                continue

            print(f"Processing: {gloss} - {video_id}")
            cap = cv2.VideoCapture(video_path)
            
            frames_landmarks = []
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Convert BGR to RGB for mediapipe
                image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = hands.process(image)
                
                frame_data = np.zeros(42*3) # 21 landmarks * 3 coords * 2 hands
                if results.multi_hand_landmarks:
                    for i, hand_landmarks in enumerate(results.multi_hand_landmarks[:2]):
                        for j, lm in enumerate(hand_landmarks.landmark):
                            # Append x, y, z normalized coordinates
                            idx = i * 63 + j * 3
                            frame_data[idx] = lm.x
                            frame_data[idx+1] = lm.y
                            frame_data[idx+2] = lm.z
                
                frames_landmarks.append(frame_data)
            
            cap.release()
            
            # WLASL videos vary in length. We need to pad or trim them to a fixed length (e.g., 30 frames)
            # This is critical for ML models like LSTM or Random Forests
            if len(frames_landmarks) > 0:
                frames_landmarks = np.array(frames_landmarks)
                if len(frames_landmarks) > SEQUENCE_LENGTH:
                    frames_landmarks = frames_landmarks[:SEQUENCE_LENGTH]
                else:
                    padding = np.zeros((SEQUENCE_LENGTH - len(frames_landmarks), 42*3))
                    frames_landmarks = np.vstack((frames_landmarks, padding))
                
                X.append(frames_landmarks)
                Y.append(gloss)

    # Save extracted Numpy files
    np.save(OUTPUT_FEATURES, np.array(X))
    np.save(OUTPUT_LABELS, np.array(Y))
    print(f"Extraction Complete! Saved {len(X)} samples.")

if __name__ == "__main__":
    extract_wlasl_features()
