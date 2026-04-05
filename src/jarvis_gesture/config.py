from dataclasses import dataclass
import os

from dotenv import load_dotenv


def _to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class AppConfig:
    camera_backend: str = "auto"
    camera_index: int = 0
    camera_fps: int = 30
    frame_width: int = 1280
    frame_height: int = 720
    gst_pipeline_profile: str = "balanced"
    gst_pipeline: str = ""

    gesture_backend: str = "auto"
    gesture_model_path: str = ""
    min_detection_confidence: float = 0.6
    min_tracking_confidence: float = 0.5
    gesture_min_confidence: float = 0.6
    gesture_smoothing_window: int = 4

    gesture_cooldown_seconds: float = 1.0
    snapshot_dir: str = "artifacts/snapshots"

    use_voice: bool = False
    tts_backend: str = "piper"
    piper_binary: str = "piper"
    piper_model_path: str = ""

    @staticmethod
    def from_env() -> "AppConfig":
        load_dotenv()
        return AppConfig(
            camera_backend=os.getenv("CAMERA_BACKEND", "auto"),
            camera_index=int(os.getenv("CAMERA_INDEX", "0")),
            camera_fps=int(os.getenv("CAMERA_FPS", "30")),
            frame_width=int(os.getenv("FRAME_WIDTH", "1280")),
            frame_height=int(os.getenv("FRAME_HEIGHT", "720")),
            gst_pipeline_profile=os.getenv("GST_PROFILE", "balanced"),
            gst_pipeline=os.getenv("GST_PIPELINE", ""),
            gesture_backend=os.getenv("GESTURE_BACKEND", "auto"),
            gesture_model_path=os.getenv("GESTURE_MODEL_PATH", ""),
            min_detection_confidence=float(os.getenv("MIN_DETECTION_CONF", "0.6")),
            min_tracking_confidence=float(os.getenv("MIN_TRACKING_CONF", "0.5")),
            gesture_min_confidence=float(os.getenv("GESTURE_MIN_CONF", "0.6")),
            gesture_smoothing_window=int(os.getenv("GESTURE_SMOOTHING_WINDOW", "4")),
            gesture_cooldown_seconds=float(os.getenv("GESTURE_COOLDOWN", "1.0")),
            snapshot_dir=os.getenv("SNAPSHOT_DIR", "artifacts/snapshots"),
            use_voice=_to_bool(os.getenv("USE_VOICE", "false")),
            tts_backend=os.getenv("TTS_BACKEND", "piper"),
            piper_binary=os.getenv("PIPER_BINARY", "piper"),
            piper_model_path=os.getenv("PIPER_MODEL_PATH", ""),
        )
