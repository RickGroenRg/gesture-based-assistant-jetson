from __future__ import annotations

import time
import cv2
import numpy as np
from typing import Optional


class CameraStream:
    def __init__(
        self,
        camera_index: int = 0,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        camera_backend: str = "auto",
        gst_profile: str = "balanced",
        gst_pipeline: str = "",
    ) -> None:
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        self.camera_backend = camera_backend
        self.gst_profile = gst_profile
        self.gst_pipeline = gst_pipeline
        self.cap: Optional[cv2.VideoCapture] = None
        self._frame_count = 0
        self._fps_window_start = time.time()
        self._rolling_fps = 0.0

    def open(self) -> None:
        backend = self.camera_backend.strip().lower()
        if backend not in {"auto", "gstreamer", "index"}:
            backend = "auto"

        if backend in {"auto", "gstreamer"}:
            pipeline = self.gst_pipeline.strip() or self._build_gstreamer_pipeline(self.gst_profile)
            self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
            if self.cap.isOpened():
                print(f"[camera] backend=gstreamer profile={self.gst_profile}")
                return
            if backend == "gstreamer":
                raise RuntimeError("Unable to open GStreamer camera stream.")

        self.cap = cv2.VideoCapture(self.camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        if not self.cap.isOpened():
            raise RuntimeError("Unable to open camera stream with any backend.")
        print("[camera] backend=index")

    def _build_gstreamer_pipeline(self, profile: str) -> str:
        profile_name = profile.strip().lower()
        width = self.width
        height = self.height
        fps = self.fps

        if profile_name == "low_latency":
            width, height, fps = 960, 540, 60
        elif profile_name == "high_detail":
            width, height, fps = 1920, 1080, 30

        return (
            f"nvarguscamerasrc sensor-id={self.camera_index} ! "
            f"video/x-raw(memory:NVMM),width={width},height={height},framerate={fps}/1,format=NV12 ! "
            "nvvidconv flip-method=0 ! "
            "video/x-raw,format=BGRx ! "
            "videoconvert ! "
            "video/x-raw,format=BGR ! "
            "appsink drop=true max-buffers=1 sync=false"
        )

    def read(self) -> np.ndarray:
        if self.cap is None:
            raise RuntimeError("Camera has not been opened.")

        ok, frame = self.cap.read()
        if not ok:
            raise RuntimeError("Failed to read frame from camera.")

        self._frame_count += 1
        elapsed = time.time() - self._fps_window_start
        if elapsed >= 1.0:
            self._rolling_fps = self._frame_count / elapsed
            self._frame_count = 0
            self._fps_window_start = time.time()

        return frame

    def get_fps(self) -> float:
        return self._rolling_fps

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
