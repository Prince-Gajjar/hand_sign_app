import os
import cv2 # pyre-ignore # type: ignore
import mediapipe as mp # pyre-ignore # type: ignore
import numpy as np # pyre-ignore # type: ignore
import pickle
import typing
from typing import cast, List, Any
from tqdm import tqdm # pyre-ignore # type: ignore
from sklearn.ensemble import RandomForestClassifier # pyre-ignore # type: ignore
from sklearn.model_selection import train_test_split # pyre-ignore # type: ignore
from sklearn.metrics import accuracy_score # pyre-ignore # type: ignore

# Configuration
DATASET_DIR = "asl_dataset/train"
MODEL_PATH = "models/gesture_model.pkl"
SAMPLES_PER_CLASS = 300  # Number of images to process per letter (keeps it fast)
IMAGE_SIZE = 224

# Initialize MediaPipe
mp_hands = mp.solutions.hands # pyre-ignore # type: ignore
hands = mp_hands.Hands(
    static_image_mode=True, 
    max_num_hands=1, 
    min_detection_confidence=0.5
)

def extract_landmarks(image):
    """Extracts 21 hand landmarks (x, y, z), centers them at the wrist, and scales them."""
    img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = hands.process(img_rgb)
    
    if results.multi_hand_landmarks:
        hand_lms = results.multi_hand_landmarks[0]
        
        # 1. Centering (Relative to Wrist - Landmark 0)
        wrist_x, wrist_y, wrist_z = hand_lms.landmark[0].x, hand_lms.landmark[0].y, hand_lms.landmark[0].z
        temp_list = []
        for lm in hand_lms.landmark:
            temp_list.extend([lm.x - wrist_x, lm.y - wrist_y, lm.z - wrist_z])
            
        # 2. Scaling (Position Invariant)
        abs_vals = [abs(v) for v in temp_list]
        max_val = max(abs_vals) if abs_vals else 0
        if max_val > 0:
            return [float(v / max_val) for v in temp_list] # type: ignore
        return temp_list
    return None

def main():
    data = []
    labels = []
    
    classes = sorted(os.listdir(DATASET_DIR))
    print(f"Found {len(classes)} classes: {classes}")
    
    print("\nExtracting features from images...")
    for label in classes:
        class_dir = os.path.join(DATASET_DIR, label)
        if not os.path.isdir(class_dir):
            continue
            
        images_list = os.listdir(class_dir)
        # Shuffle or slice to get a representative sample
        images = images_list[:int(SAMPLES_PER_CLASS)] # type: ignore
        
        count = 0
        for img_name in tqdm(images, desc=f"Class {label}"):
            img_path = os.path.join(class_dir, img_name)
            img = cv2.imread(img_path)
            
            if img is None:
                continue
                
            landmarks = extract_landmarks(img)
            if landmarks:
                data.append(landmarks)
                labels.append(label)
                count = cast(int, count) + 1
                
        print(f"  Successfully processed {count}/{len(images)} images for class {label}")

    X = np.array(data)
    y = np.array(labels)

    if len(X) == 0:
        print("Error: No features extracted. Check your dataset path and images.")
        return

    print(f"\nTotal samples collected: {len(X)}")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    print("Training Random Forest model...")
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"\nModel Accuracy: {accuracy * 100:.2f}%")
    
    # Save model and meta-data
    print(f"Saving model to {MODEL_PATH}...")
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    
    model_data = {
        'model': model,
        'labels': classes,
        'accuracy': accuracy
    }
    
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(model_data, f)
        
    print("Training Complete!")

if __name__ == "__main__":
    main()
