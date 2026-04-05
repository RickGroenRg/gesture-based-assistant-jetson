from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
import math
from typing import Deque, Dict, Optional, Tuple

import cv2
import numpy as np

try:
    import mediapipe as mp
except Exception:
    mp = None

try:
    from mediapipe.tasks import python as mp_tasks
    from mediapipe.tasks.python import vision as mp_vision
except Exception:
    mp_tasks = None
    mp_vision = None


@dataclass
class GestureResult:
    name: str
    confidence: float


class _RuleGestureBackend:
    def __init__(self, min_detection_confidence: float = 0.6, min_tracking_confidence: float = 0.5) -> None:
        self.available = mp is not None
        self._hands = None
        self._drawer = None
        self._hand_connections = None

        if self.available:
            self._hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
            self._drawer = mp.solutions.drawing_utils
            self._hand_connections = mp.solutions.hands.HAND_CONNECTIONS

    def detect(self, frame: np.ndarray) -> Tuple[np.ndarray, Optional[GestureResult]]:
        if not self.available:
            return frame, None

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._hands.process(rgb)
        if not results.multi_hand_landmarks:
            return frame, None

        hand_landmarks = results.multi_hand_landmarks[0]
        self._drawer.draw_landmarks(frame, hand_landmarks, self._hand_connections)

        landmarks = hand_landmarks.landmark

        thumb_tip = landmarks[4]
        index_tip = landmarks[8]
        middle_tip = landmarks[12]
        ring_tip = landmarks[16]
        pinky_tip = landmarks[20]

        wrist = landmarks[0]
        index_mcp = landmarks[5]
        pinky_mcp = landmarks[17]

        hand_size = math.dist((index_mcp.x, index_mcp.y), (pinky_mcp.x, pinky_mcp.y))
        if hand_size < 1e-4:
            return frame, None

        finger_spread = (
            math.dist((thumb_tip.x, thumb_tip.y), (index_tip.x, index_tip.y))
            + math.dist((index_tip.x, index_tip.y), (middle_tip.x, middle_tip.y))
            + math.dist((middle_tip.x, middle_tip.y), (ring_tip.x, ring_tip.y))
            + math.dist((ring_tip.x, ring_tip.y), (pinky_tip.x, pinky_tip.y))
        ) / hand_size

        finger_heights = [index_tip.y, middle_tip.y, ring_tip.y, pinky_tip.y]
        avg_tip_height = sum(finger_heights) / len(finger_heights)

        if finger_spread > 2.2 and avg_tip_height < wrist.y:
            return frame, GestureResult(name="open_palm", confidence=min(1.0, finger_spread / 3.0))

        if finger_spread < 1.2 and avg_tip_height > wrist.y - 0.05:
            return frame, GestureResult(name="fist", confidence=0.75)

        return frame, None

    def close(self) -> None:
        if self._hands is not None:
            self._hands.close()


class _TasksGestureBackend:
    _TASK_TO_INTENT: Dict[str, str] = {
        "Open_Palm": "open_palm",
        "Closed_Fist": "fist",
        "Thumb_Up": "thumbs_up",
        "Pointing_Up": "point_up",
        "Victory": "victory",
        "ILoveYou": "i_love_you",
    }

    def __init__(
        self,
        model_path: str,
        min_detection_confidence: float = 0.6,
        min_tracking_confidence: float = 0.5,
        min_confidence: float = 0.6,
    ) -> None:
        self.available = False
        self.min_confidence = min_confidence
        self._recognizer = None

        if not model_path or mp is None or mp_tasks is None or mp_vision is None:
            return

        options = mp_vision.GestureRecognizerOptions(
            base_options=mp_tasks.BaseOptions(model_asset_path=model_path),
            running_mode=mp_vision.RunningMode.IMAGE,
            num_hands=1,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._recognizer = mp_vision.GestureRecognizer.create_from_options(options)
        self.available = True

    def detect(self, frame: np.ndarray) -> Tuple[np.ndarray, Optional[GestureResult]]:
        if not self.available or self._recognizer is None:
            return frame, None

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._recognizer.recognize(mp_image)

        if not result.gestures or not result.gestures[0]:
            return frame, None

        top = result.gestures[0][0]
        if top.score < self.min_confidence:
            return frame, None

        mapped = self._TASK_TO_INTENT.get(top.category_name)
        if mapped is None:
            return frame, None

        return frame, GestureResult(name=mapped, confidence=top.score)

    def close(self) -> None:
        if self._recognizer is not None:
            self._recognizer.close()


class GestureRecognizer:
    def __init__(
        self,
        min_detection_confidence: float = 0.6,
        min_tracking_confidence: float = 0.5,
        backend: str = "auto",
        model_path: str = "",
        min_confidence: float = 0.6,
        smoothing_window: int = 4,
    ) -> None:
        self.backend_name = "rules"
        self._history: Deque[str] = deque(maxlen=max(1, smoothing_window))

        backend_name = backend.strip().lower()
        if backend_name in {"auto", "mediapipe_tasks"}:
            tasks_backend = _TasksGestureBackend(
                model_path=model_path,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
                min_confidence=min_confidence,
            )
            if tasks_backend.available:
                self._backend = tasks_backend
                self.backend_name = "mediapipe_tasks"
                return

        self._backend = _RuleGestureBackend(
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self.backend_name = "rules"

    def detect(self, frame: np.ndarray) -> Tuple[np.ndarray, Optional[GestureResult]]:
        frame, result = self._backend.detect(frame)
        if result is None:
            self._history.clear()
            return frame, None

        self._history.append(result.name)
        majority_name, count = Counter(self._history).most_common(1)[0]
        if count < max(1, len(self._history) // 2 + 1):
            return frame, None

        return frame, GestureResult(name=majority_name, confidence=result.confidence)

    def close(self) -> None:
        self._backend.close()
