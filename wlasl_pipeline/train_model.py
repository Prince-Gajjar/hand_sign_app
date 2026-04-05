import numpy as np
import pickle
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

FEATURES_FILE = "wlasl_features.npy"
LABELS_FILE = "wlasl_labels.npy"
MODEL_OUTPUT = "../models/gesture_model.pkl"

def train_model():
    print("Loading extracted MediaPipe features...")
    # shape: (Num_Videos, Sequence_Length, 126_Landmark_Coordinates)
    X = np.load(FEATURES_FILE)
    Y = np.load(LABELS_FILE)

    # Scikit-Learn models expect 2D arrays (Rows=Samples, Cols=Features)
    # We flatten the Sequence_Length * 126_Landmarks down to a 1D array per video.
    num_samples, seq_length, num_features = X.shape
    X_flattened = X.reshape(num_samples, seq_length * num_features)

    # Label encoding (convert string names to integers)
    classes = np.unique(Y)
    label_map = {name: idx for idx, name in enumerate(classes)}
    Y_encoded = np.array([label_map[y] for y in Y])

    # Split dataset (80% training, 20% testing)
    X_train, X_test, y_train, y_test = train_test_split(X_flattened, Y_encoded, test_size=0.2, random_state=42)

    print(f"Training on {len(X_train)} video sequences...")
    # RandomForest works impressively well on flattened sequential heuristics
    clf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    clf.fit(X_train, y_train)

    print("Evaluating Model...")
    predictions = clf.predict(X_test)
    accuracy = accuracy_score(y_test, predictions)
    print(f"Validation Accuracy: {accuracy * 100:.2f}%")

    # We need to save the mapping dictionary alongside the model so the app knows what '0' or '1' means
    model_data = {
        'model': clf,
        'label_map': {v: k for k, v in label_map.items()} # Reverse map: 0 -> "hello"
    }

    # Export to the main app's models directory
    with open(MODEL_OUTPUT, 'wb') as f:
        pickle.dump(model_data, f)
    
    print(f"Success! Model exported to {MODEL_OUTPUT}")

if __name__ == '__main__':
    train_model()
