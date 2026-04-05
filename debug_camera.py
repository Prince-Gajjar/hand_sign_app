import cv2  # pyre-ignore
import time

def test_camera(idx, backend=None):
    if backend:
        print(f"Testing index {idx} with backend {backend}...")
        cap = cv2.VideoCapture(idx, backend)
    else:
        print(f"Testing index {idx} with default backend...")
        cap = cv2.VideoCapture(idx)
        
    start = time.time()
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            print(f"SUCCESS: Index {idx} works. Frame shape: {frame.shape}")
        else:
            print(f"FAILED: Index {idx} is opened but cannot read frame.")
        cap.release()
    else:
        print(f"FAILED: Index {idx} cannot be opened.")
    print(f"Time taken: {time.time() - start:.2f}s")
    print("-" * 20)

if __name__ == "__main__":
    for i in range(2):
        test_camera(i)
        test_camera(i, cv2.CAP_DSHOW)
        test_camera(i, cv2.CAP_MSMF)
