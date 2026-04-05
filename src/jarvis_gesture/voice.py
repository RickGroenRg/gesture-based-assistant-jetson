from __future__ import annotations

from dataclasses import dataclass
import queue
import shutil
import subprocess
import threading
from typing import Optional

try:
    import pyttsx3
except Exception:
    pyttsx3 = None

try:
    import speech_recognition as sr
except Exception:
    sr = None


@dataclass
class VoiceCommand:
    intent: Optional[str]
    text: str


class VoiceIO:
    def __init__(
        self,
        enabled: bool = False,
        backend: str = "piper",
        piper_binary: str = "piper",
        piper_model_path: str = "",
    ) -> None:
        self.requested_enabled = enabled
        self.backend = "none"
        self.piper_binary = piper_binary
        self.piper_model_path = piper_model_path
        self.enabled = False
        self._stop_event = threading.Event()
        self._queue: "queue.Queue[str]" = queue.Queue(maxsize=20)
        self._worker: Optional[threading.Thread] = None
        self.engine = None
        self.recognizer = sr.Recognizer() if sr is not None else None

        self._initialize_backend(backend)
        if self.enabled:
            self._worker = threading.Thread(target=self._worker_loop, daemon=True)
            self._worker.start()

    def speak(self, text: str) -> None:
        if not self.enabled:
            return

        message = text.strip()
        if not message:
            return

        try:
            self._queue.put_nowait(message)
        except queue.Full:
            # Drop oldest to keep interaction responsive under bursty events.
            try:
                _ = self._queue.get_nowait()
                self._queue.put_nowait(message)
            except queue.Empty:
                pass

    def poll_command(self) -> Optional[VoiceCommand]:
        if not self.enabled or self.recognizer is None or sr is None:
            return None
        return None

    def close(self) -> None:
        if not self.enabled:
            return

        self._stop_event.set()
        if self._worker is not None:
            self._worker.join(timeout=2.0)

    def _initialize_backend(self, backend: str) -> None:
        if not self.requested_enabled:
            return

        backend_name = backend.strip().lower()
        if backend_name in {"piper", "auto"} and self._can_use_piper():
            self.backend = "piper"
            self.enabled = True
            print("[voice] backend=piper")
            return

        if backend_name in {"pyttsx3", "auto", "piper"} and pyttsx3 is not None:
            try:
                self.engine = pyttsx3.init()
                self.backend = "pyttsx3"
                self.enabled = True
                print("[voice] backend=pyttsx3")
                return
            except Exception:
                self.engine = None

        if backend_name in {"espeak", "auto", "piper", "pyttsx3"} and shutil.which("espeak-ng"):
            self.backend = "espeak"
            self.enabled = True
            print("[voice] backend=espeak")
            return

        print("[voice] disabled (no usable TTS backend)")

    def _can_use_piper(self) -> bool:
        return (
            bool(self.piper_model_path)
            and shutil.which(self.piper_binary) is not None
            and shutil.which("aplay") is not None
        )

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                text = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                if self.backend == "piper":
                    self._speak_piper(text)
                elif self.backend == "pyttsx3":
                    self._speak_pyttsx3(text)
                elif self.backend == "espeak":
                    self._speak_espeak(text)
            except Exception as exc:
                print(f"[voice] speak error: {exc}")

    def _speak_piper(self, text: str) -> None:
        piper_cmd = [self.piper_binary, "--model", self.piper_model_path, "--output-raw"]
        aplay_cmd = ["aplay", "-r", "22050", "-f", "S16_LE", "-t", "raw", "-"]

        piper_proc = subprocess.Popen(
            piper_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )

        aplay_proc = subprocess.Popen(
            aplay_cmd,
            stdin=piper_proc.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if piper_proc.stdin is not None:
            piper_proc.stdin.write(text)
            piper_proc.stdin.close()

        piper_proc.wait(timeout=15)
        aplay_proc.wait(timeout=15)

    def _speak_pyttsx3(self, text: str) -> None:
        if self.engine is None:
            return
        self.engine.say(text)
        self.engine.runAndWait()

    def _speak_espeak(self, text: str) -> None:
        subprocess.run(["espeak-ng", text], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
