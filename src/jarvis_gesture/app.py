from __future__ import annotations

import time
import cv2

from .actions import ActionRouter
from .camera import CameraStream
from .config import AppConfig
from .gestures import GestureRecognizer
from .voice import VoiceIO


class JarvisGestureApp:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.camera = CameraStream(
            camera_index=config.camera_index,
            width=config.frame_width,
            height=config.frame_height,
            fps=config.camera_fps,
            camera_backend=config.camera_backend,
            gst_profile=config.gst_pipeline_profile,
            gst_pipeline=config.gst_pipeline,
        )
        self.gesture = GestureRecognizer(
            min_detection_confidence=config.min_detection_confidence,
            min_tracking_confidence=config.min_tracking_confidence,
            backend=config.gesture_backend,
            model_path=config.gesture_model_path,
            min_confidence=config.gesture_min_confidence,
            smoothing_window=config.gesture_smoothing_window,
        )
        self.actions = ActionRouter(config.snapshot_dir)
        self.voice = VoiceIO(
            enabled=config.use_voice,
            backend=config.tts_backend,
            piper_binary=config.piper_binary,
            piper_model_path=config.piper_model_path,
        )
        self.last_trigger_ts = 0.0

    def run(self) -> None:
        self.camera.open()
        print(f"[gesture] backend={self.gesture.backend_name}")
        self.voice.speak("Jarvis gesture assistant initialized")

        try:
            while True:
                frame = self.camera.read()
                frame, gesture_result = self.gesture.detect(frame)

                if gesture_result is not None:
                    now = time.time()
                    if now - self.last_trigger_ts >= self.config.gesture_cooldown_seconds:
                        self.last_trigger_ts = now
                        action_result = self.actions.execute(gesture_result.name, frame)
                        if action_result.ok:
                            self.voice.speak(action_result.message)
                        cv2.putText(
                            frame,
                            f"{gesture_result.name}: {gesture_result.confidence:.2f}",
                            (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1,
                            (0, 255, 0),
                            2,
                        )

                cv2.putText(frame, "Press q to quit", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
                cv2.putText(
                    frame,
                    f"FPS: {self.camera.get_fps():.1f}",
                    (20, 120),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 255, 255),
                    2,
                )
                cv2.imshow("Jarvis Gesture Assistant", frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break

        finally:
            self.gesture.close()
            self.voice.close()
            self.camera.close()
            cv2.destroyAllWindows()
