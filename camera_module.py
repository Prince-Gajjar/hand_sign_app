import cv2  # pyre-ignore # type: ignore
from kivy.logger import Logger
import threading
import time
import numpy as np

class CameraFeed:
    """Optimized Camera Feed using a double-buffering strategy to minimize GC pressure."""
    MAX_RETRIES = 3

    def __init__(self):
        self.camera_index = 0
        self.cap = None
        self.ret = False
        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        self._consecutive_failures = 0
        self._init_camera()

    def _init_camera(self):
        try:
            self.running = False
            time.sleep(0.05)

            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None

            Logger.info(f"Camera: Opening camera {self.camera_index}...")
            # Use CAP_DSHOW on Windows for faster init, or default on other platforms
            try:
                self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            except Exception:
                self.cap = cv2.VideoCapture(self.camera_index)

            if self.cap is not None and self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                # Try MJPG for performance
                self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

                self._consecutive_failures = 0
                self.running = True
                t = threading.Thread(target=self._update_frame, daemon=True, name="CameraFeedThread")
                t.start()
                Logger.info("Camera: Thread started")
            else:
                Logger.error(f"Camera: Failed to open camera {self.camera_index}")
        except Exception as e:
            Logger.error(f"Camera: _init_camera crashed: {e}")

    def _update_frame(self):
        """Continuously reads frames from camera on background thread."""
        while self.running:
            try:
                cap_obj = self.cap
                if cap_obj and cap_obj.isOpened():
                    ret, frame = cap_obj.read()
                    if ret and frame is not None:
                        with self.lock:
                            self.ret = ret
                            # We store the reference. The UI thread will copy if it needs persistence.
                            self.frame = frame
                            self._consecutive_failures = 0
                    else:
                        self._consecutive_failures += 1
                        if self._consecutive_failures > 30:
                            self._reconnect()
                else:
                    time.sleep(0.5)
            except Exception as e:
                Logger.warning(f"Camera: loop error: {e}")
                time.sleep(0.1)
            time.sleep(0.01) # Approx 100fps max internal cap

    def _reconnect(self):
        Logger.warning("Camera: Attempting reconnect...")
        self._consecutive_failures = 0
        try:
            if self.cap: self.cap.release()
            self.cap = cv2.VideoCapture(self.camera_index)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

    def switch_camera(self):
        self.camera_index = 1 if self.camera_index == 0 else 0
        self._init_camera()

    def get_frame(self):
        """Retrieve latest frame. Returns (success, frame_reference)."""
        with self.lock:
            if self.ret and self.frame is not None:
                # We return the reference to avoid unnecessary copies.
                # CALLER MUST COPY if they intend to process it while the camera thread continues.
                return True, self.frame
        return False, None

    def release(self):
        self.running = False
        time.sleep(0.1)
        if self.cap:
            self.cap.release()
            self.cap = None
