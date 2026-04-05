from __future__ import annotations

import logging
import os
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
        self._configure_logging()
        self.logger = logging.getLogger("jarvis_gesture.app")
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
            microphone_enabled=config.microphone_enabled,
            microphone_device_index=config.microphone_device_index,
            stt_timeout_seconds=config.stt_timeout_seconds,
            stt_phrase_time_limit_seconds=config.stt_phrase_time_limit_seconds,
            stt_calibration_seconds=config.stt_calibration_seconds,
        )
        self.last_trigger_ts = 0.0
        self.display_enabled = self._should_display_frames()

    def _configure_logging(self) -> None:
        level_name = self.config.log_level.strip().upper() if self.config.log_level else "INFO"
        level = getattr(logging, level_name, logging.INFO)
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        )

    def _should_display_frames(self) -> bool:
        mode = self.config.display_mode.strip().lower()
        if mode == "always":
            return True
        if mode == "never":
            return False
        if os.name == "nt":
            return True
        return bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))

    def run(self) -> None:
        self.camera.open()
        self.logger.info("gesture backend=%s", self.gesture.backend_name)
        self.logger.info("display enabled=%s (mode=%s)", self.display_enabled, self.config.display_mode)
        self.logger.info("microphone enabled=%s stt_enabled=%s", self.config.microphone_enabled, self.voice.stt_enabled)
        self.voice.speak("Jarvis gesture assistant initialized")

        metrics_started_at = time.time()
        last_metrics_log = metrics_started_at
        loop_count = 0
        gesture_count = 0
        action_success = 0
        action_failed = 0
        total_loop_time = 0.0

        try:
            while True:
                loop_started = time.time()
                frame = self.camera.read()
                frame, gesture_result = self.gesture.detect(frame)
                loop_count += 1

                voice_command = self.voice.poll_command()
                if voice_command is not None:
                    self.logger.info("stt text=%s intent=%s", voice_command.text, voice_command.intent)
                    if voice_command.intent == "discussion_options":
                        help_text = (
                            "You can say play pause, volume up, volume down, snapshot, or ask for discussion options."
                        )
                        self.voice.speak(help_text)
                    elif voice_command.intent is not None:
                        action_result = self.actions.execute(voice_command.intent, frame)
                        if action_result.ok:
                            action_success += 1
                            self.logger.info(
                                "voice intent=%s action_ok message=%s",
                                voice_command.intent,
                                action_result.message,
                            )
                            self.voice.speak(action_result.message)
                        else:
                            action_failed += 1
                            self.logger.warning(
                                "voice intent=%s action_failed message=%s",
                                voice_command.intent,
                                action_result.message,
                            )

                if gesture_result is not None:
                    gesture_count += 1
                    now = time.time()
                    if now - self.last_trigger_ts >= self.config.gesture_cooldown_seconds:
                        self.last_trigger_ts = now
                        action_result = self.actions.execute(gesture_result.name, frame)
                        if action_result.ok:
                            action_success += 1
                            self.voice.speak(action_result.message)
                            self.logger.info(
                                "intent=%s confidence=%.2f action_ok message=%s",
                                gesture_result.name,
                                gesture_result.confidence,
                                action_result.message,
                            )
                        else:
                            action_failed += 1
                            self.logger.warning(
                                "intent=%s confidence=%.2f action_failed message=%s",
                                gesture_result.name,
                                gesture_result.confidence,
                                action_result.message,
                            )

                        if self.display_enabled:
                            cv2.putText(
                                frame,
                                f"{gesture_result.name}: {gesture_result.confidence:.2f}",
                                (20, 40),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                1,
                                (0, 255, 0),
                                2,
                            )

                loop_ms = (time.time() - loop_started) * 1000.0
                total_loop_time += loop_ms

                if self.display_enabled:
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

                now = time.time()
                if now - last_metrics_log >= self.config.metrics_log_interval_seconds:
                    runtime = max(0.001, now - metrics_started_at)
                    avg_loop_ms = total_loop_time / max(1, loop_count)
                    self.logger.info(
                        "metrics runtime=%.1fs fps=%.1f loops=%d gestures=%d actions_ok=%d actions_failed=%d avg_loop_ms=%.2f",
                        runtime,
                        self.camera.get_fps(),
                        loop_count,
                        gesture_count,
                        action_success,
                        action_failed,
                        avg_loop_ms,
                    )
                    last_metrics_log = now
        except KeyboardInterrupt:
            self.logger.info("shutdown requested by user")
        except Exception:
            self.logger.exception("runtime error in main loop")
            raise

        finally:
            self.gesture.close()
            self.voice.close()
            self.camera.close()
            if self.display_enabled:
                cv2.destroyAllWindows()
