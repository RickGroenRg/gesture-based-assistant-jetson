from __future__ import annotations

from dataclasses import dataclass
import queue
import re
import shutil
import subprocess
import threading
import time
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
        microphone_enabled: bool = False,
        microphone_device_index: int = -1,
        stt_timeout_seconds: float = 2.0,
        stt_phrase_time_limit_seconds: float = 4.0,
        stt_calibration_seconds: float = 0.5,
    ) -> None:
        self.requested_tts_enabled = enabled
        self.requested_microphone_enabled = microphone_enabled
        self.backend = "none"
        self.piper_binary = piper_binary
        self.piper_model_path = piper_model_path
        self.microphone_device_index = microphone_device_index
        self.stt_timeout_seconds = stt_timeout_seconds
        self.stt_phrase_time_limit_seconds = stt_phrase_time_limit_seconds
        self.stt_calibration_seconds = stt_calibration_seconds

        self.tts_enabled = False
        self.stt_enabled = False
        self._stop_event = threading.Event()
        self._tts_queue: "queue.Queue[str]" = queue.Queue(maxsize=20)
        self._stt_queue: "queue.Queue[VoiceCommand]" = queue.Queue(maxsize=20)
        self._tts_worker: Optional[threading.Thread] = None
        self._stt_worker: Optional[threading.Thread] = None
        self.engine = None
        self.recognizer = sr.Recognizer() if sr is not None else None

        self._initialize_tts_backend(backend)
        self._initialize_stt_backend()

        if self.tts_enabled:
            self._tts_worker = threading.Thread(target=self._tts_worker_loop, daemon=True)
            self._tts_worker.start()

        if self.stt_enabled:
            self._stt_worker = threading.Thread(target=self._stt_worker_loop, daemon=True)
            self._stt_worker.start()

    def speak(self, text: str) -> None:
        if not self.tts_enabled:
            return

        message = text.strip()
        if not message:
            return

        try:
            self._tts_queue.put_nowait(message)
        except queue.Full:
            # Drop oldest to keep interaction responsive under bursty events.
            try:
                _ = self._tts_queue.get_nowait()
                self._tts_queue.put_nowait(message)
            except queue.Empty:
                pass

    def poll_command(self) -> Optional[VoiceCommand]:
        if not self.stt_enabled:
            return None

        try:
            return self._stt_queue.get_nowait()
        except queue.Empty:
            return None

    def close(self) -> None:
        self._stop_event.set()

        if self._tts_worker is not None:
            self._tts_worker.join(timeout=2.0)

        if self._stt_worker is not None:
            self._stt_worker.join(timeout=2.0)

    def _initialize_tts_backend(self, backend: str) -> None:
        if not self.requested_tts_enabled:
            return

        backend_name = backend.strip().lower()
        if backend_name in {"piper", "auto"} and self._can_use_piper():
            self.backend = "piper"
            self.tts_enabled = True
            print("[voice] backend=piper")
            return

        if backend_name in {"pyttsx3", "auto", "piper"} and pyttsx3 is not None:
            try:
                self.engine = pyttsx3.init()
                self.backend = "pyttsx3"
                self.tts_enabled = True
                print("[voice] backend=pyttsx3")
                return
            except Exception:
                self.engine = None

        if backend_name in {"espeak", "auto", "piper", "pyttsx3"} and shutil.which("espeak-ng"):
            self.backend = "espeak"
            self.tts_enabled = True
            print("[voice] backend=espeak")
            return

        print("[voice] disabled (no usable TTS backend)")

    def _initialize_stt_backend(self) -> None:
        if not self.requested_microphone_enabled:
            return

        if sr is None or self.recognizer is None:
            print("[stt] disabled (SpeechRecognition unavailable)")
            return

        self.stt_enabled = True
        mic_desc = "default" if self.microphone_device_index < 0 else str(self.microphone_device_index)
        print(f"[stt] microphone enabled device={mic_desc}")

    def _can_use_piper(self) -> bool:
        return (
            bool(self.piper_model_path)
            and shutil.which(self.piper_binary) is not None
            and shutil.which("aplay") is not None
        )

    def _tts_worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                text = self._tts_queue.get(timeout=0.1)
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

    def _stt_worker_loop(self) -> None:
        if sr is None or self.recognizer is None:
            return

        mic_index = None if self.microphone_device_index < 0 else self.microphone_device_index
        try:
            with sr.Microphone(device_index=mic_index) as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=self.stt_calibration_seconds)

                while not self._stop_event.is_set():
                    try:
                        audio = self.recognizer.listen(
                            source,
                            timeout=self.stt_timeout_seconds,
                            phrase_time_limit=self.stt_phrase_time_limit_seconds,
                        )
                    except sr.WaitTimeoutError:
                        continue
                    except Exception as exc:
                        print(f"[stt] listen error: {exc}")
                        time.sleep(0.2)
                        continue

                    try:
                        text = self.recognizer.recognize_google(audio)
                    except sr.UnknownValueError:
                        continue
                    except sr.RequestError as exc:
                        print(f"[stt] recognition request error: {exc}")
                        time.sleep(0.5)
                        continue
                    except Exception as exc:
                        print(f"[stt] recognition error: {exc}")
                        continue

                    normalized = self._normalize_text(text)
                    if not normalized:
                        continue

                    intent = self._map_intent(normalized)
                    cmd = VoiceCommand(intent=intent, text=normalized)
                    try:
                        self._stt_queue.put_nowait(cmd)
                    except queue.Full:
                        try:
                            _ = self._stt_queue.get_nowait()
                            self._stt_queue.put_nowait(cmd)
                        except queue.Empty:
                            pass
        except Exception as exc:
            print(f"[stt] disabled due to microphone error: {exc}")
            self.stt_enabled = False

    def _normalize_text(self, text: str) -> str:
        lowered = text.lower().strip()
        lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
        return re.sub(r"\s+", " ", lowered).strip()

    def _map_intent(self, text: str) -> Optional[str]:
        phrases = [
            ("discussion_options", ["discussion options", "what can i say", "what are my commands", "command list", "help", "options"]),
            ("voice_volume_up", ["volume up", "turn it up", "louder", "increase volume", "raise volume", "sound up"]),
            ("voice_volume_down", ["volume down", "turn it down", "quieter", "decrease volume", "lower volume", "sound down"]),
            ("voice_snapshot", ["take snapshot", "take photo", "take picture", "capture image", "snapshot", "capture"]),
            ("voice_play_pause", ["play pause", "toggle playback", "play", "pause", "resume"]),
        ]

        for intent, candidates in phrases:
            for phrase in candidates:
                if phrase in text:
                    return intent

        return None

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
