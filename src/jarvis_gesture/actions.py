from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict

import cv2
import numpy as np


@dataclass
class ActionResult:
    ok: bool
    message: str


class ActionRouter:
    def __init__(self, snapshot_dir: str) -> None:
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._handlers: Dict[str, Callable[[np.ndarray], ActionResult]] = {
            "open_palm": self._handle_play_pause,
            "fist": self._handle_snapshot,
            "voice_volume_up": self._handle_volume_up,
            "voice_volume_down": self._handle_volume_down,
        }

    def execute(self, intent_name: str, frame: np.ndarray) -> ActionResult:
        handler = self._handlers.get(intent_name)
        if handler is None:
            return ActionResult(ok=False, message=f"No action for intent: {intent_name}")
        return handler(frame)

    def _handle_play_pause(self, _: np.ndarray) -> ActionResult:
        return ActionResult(ok=True, message="Play/Pause toggled (placeholder).")

    def _handle_volume_up(self, _: np.ndarray) -> ActionResult:
        return ActionResult(ok=True, message="Volume up (placeholder).")

    def _handle_volume_down(self, _: np.ndarray) -> ActionResult:
        return ActionResult(ok=True, message="Volume down (placeholder).")

    def _handle_snapshot(self, frame: np.ndarray) -> ActionResult:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.snapshot_dir / f"snapshot_{timestamp}.jpg"
        cv2.imwrite(str(path), frame)
        return ActionResult(ok=True, message=f"Snapshot saved: {path}")
