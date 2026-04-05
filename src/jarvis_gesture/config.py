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

    microphone_enabled: bool = False
    microphone_device_index: int = -1
    stt_timeout_seconds: float = 2.0
    stt_phrase_time_limit_seconds: float = 4.0
    stt_calibration_seconds: float = 0.5

    log_level: str = "INFO"
    metrics_log_interval_seconds: float = 2.0
    display_mode: str = "auto"

    ha_enabled: bool = False
    ha_base_url: str = ""
    ha_token: str = ""
    ha_request_timeout_seconds: float = 5.0
    ha_verify_tls: bool = True
    ha_calendar_entity_id: str = ""
    ha_todo_entity_id: str = ""

    local_task_store_path: str = "artifacts/planning/tasks.json"
    local_sync_queue_path: str = "artifacts/planning/sync_queue.json"
    planning_daily_hours_limit: float = 8.0

    website_lookup_enabled: bool = True
    website_lookup_timeout_seconds: float = 4.0
    website_lookup_allowlist: str = ""

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
            microphone_enabled=_to_bool(os.getenv("MICROPHONE_ENABLED", "false")),
            microphone_device_index=int(os.getenv("MICROPHONE_DEVICE_INDEX", "-1")),
            stt_timeout_seconds=float(os.getenv("STT_TIMEOUT_SECONDS", "2.0")),
            stt_phrase_time_limit_seconds=float(os.getenv("STT_PHRASE_TIME_LIMIT_SECONDS", "4.0")),
            stt_calibration_seconds=float(os.getenv("STT_CALIBRATION_SECONDS", "0.5")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            metrics_log_interval_seconds=float(os.getenv("METRICS_LOG_INTERVAL", "2.0")),
            display_mode=os.getenv("DISPLAY_MODE", "auto"),
            ha_enabled=_to_bool(os.getenv("HA_ENABLED", "false")),
            ha_base_url=os.getenv("HA_BASE_URL", ""),
            ha_token=os.getenv("HA_TOKEN", ""),
            ha_request_timeout_seconds=float(os.getenv("HA_REQUEST_TIMEOUT_SECONDS", "5.0")),
            ha_verify_tls=_to_bool(os.getenv("HA_VERIFY_TLS", "true")),
            ha_calendar_entity_id=os.getenv("HA_CALENDAR_ENTITY_ID", ""),
            ha_todo_entity_id=os.getenv("HA_TODO_ENTITY_ID", ""),
            local_task_store_path=os.getenv("LOCAL_TASK_STORE_PATH", "artifacts/planning/tasks.json"),
            local_sync_queue_path=os.getenv("LOCAL_SYNC_QUEUE_PATH", "artifacts/planning/sync_queue.json"),
            planning_daily_hours_limit=float(os.getenv("PLANNING_DAILY_HOURS_LIMIT", "8.0")),
            website_lookup_enabled=_to_bool(os.getenv("WEBSITE_LOOKUP_ENABLED", "true")),
            website_lookup_timeout_seconds=float(os.getenv("WEBSITE_LOOKUP_TIMEOUT_SECONDS", "4.0")),
            website_lookup_allowlist=os.getenv("WEBSITE_LOOKUP_ALLOWLIST", ""),
        )
