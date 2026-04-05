# Jarvis Gesture Assistant on Jetson Orin Nano

This repository builds a practical, showcase-ready AI assistant inspired by Jarvis that understands hand gestures from an IMX219 camera and triggers real-world actions.

## Purpose

The goal is to create tools that improve everyday life while demonstrating end-to-end AI systems engineering:

- Real-time camera perception on edge hardware (Jetson Orin Nano)
- Gesture recognition for natural interaction
- Assistant orchestration with optional voice feedback
- Action execution that controls local workflows

Current implementation status: MVP foundation is in progress with a working runtime skeleton.

## MVP Scope (v0.1)

Included now:

- Live camera stream ingestion
- Hand landmark detection with MediaPipe
- Rule-based gesture intents:
  - open_palm -> play/pause placeholder action
  - fist -> snapshot action
- Action router and cooldown handling
- Optional voice output pipeline hooks

Planned in next milestones:

- Voice command input mapping (volume up/down and more)
- MediaPipe Tasks gesture backend integration with fallback
- Jetson-optimized camera pipeline (GStreamer)
- Demo scripts and reliability instrumentation

## Hardware

- Jetson Orin Nano
- IMX219 camera module

## Project Structure

- app.py: entry point
- src/jarvis_gesture/config.py: runtime configuration via environment
- src/jarvis_gesture/camera.py: camera abstraction
- src/jarvis_gesture/gestures.py: gesture recognition module
- src/jarvis_gesture/actions.py: intent-to-action routing
- src/jarvis_gesture/voice.py: voice I/O hooks
- src/jarvis_gesture/app.py: main runtime loop
- .env.example: configurable runtime defaults

## Quick Start

### 1. Jetson System Prerequisites

On Jetson Orin Nano (JetPack installed), make sure core runtime packages are present:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip python3-dev \
	gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
	gstreamer1.0-plugins-bad gstreamer1.0-libav portaudio19-dev alsa-utils espeak-ng
```

### 2. Hardware Verification (Jetson Orin + IMX219)

Before installing Python dependencies, verify the camera is detected and streams correctly.

1. Confirm the camera is visible to Argus:

```bash
gst-launch-1.0 nvarguscamerasrc sensor-id=0 num-buffers=60 ! \
	"video/x-raw(memory:NVMM),width=1280,height=720,framerate=30/1,format=NV12" ! \
	nvvidconv ! "video/x-raw,format=BGRx" ! videoconvert ! \
	"video/x-raw,format=BGR" ! fakesink
```

2. If this fails, check ribbon cable orientation, camera connector lock, and reboot.
3. If errors mention Argus, restart the daemon:

```bash
sudo systemctl restart nvargus-daemon
```

4. Re-run the gst-launch command and continue only when it succeeds.

### 3. Python Environment Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
pip install -e .
```

### 4. Required Model Dependencies

This project uses existing pretrained models. For Jetson deployment you should provide:

1. MediaPipe Tasks Gesture Recognizer model (.task file)
2. Piper TTS voice model (.onnx and matching .json config)

Recommended layout:

```text
models/
	gesture_recognizer.task
	piper/
		en_US-lessac-medium.onnx
		en_US-lessac-medium.onnx.json
```

Set environment variables in .env:

```env
GESTURE_BACKEND=mediapipe_tasks
GESTURE_MODEL_PATH=models/gesture_recognizer.task
USE_VOICE=true
TTS_BACKEND=piper
PIPER_BINARY=piper
PIPER_MODEL_PATH=models/piper/en_US-lessac-medium.onnx
CAMERA_BACKEND=gstreamer
GST_PROFILE=balanced
```

If a model is missing or fails to load, the app is designed to fall back to safer defaults where possible.

### 5. Copy Environment Template

On Linux:

```bash
cp .env.example .env
```

On PowerShell:

```powershell
Copy-Item .env.example .env
```

Then update .env with your model paths and selected backends.

### 6. Run the Application

```bash
python app.py
```

Expected startup signals:

1. Camera backend line (gstreamer or index)
2. Gesture backend line (mediapipe_tasks or rules)
3. Voice backend line (piper, pyttsx3, espeak, or disabled)

In the app window:

- Show an open palm to trigger play/pause placeholder action
- Make a fist to save a snapshot in artifacts/snapshots
- Press q to quit

### 7. Post-Setup Verification Checklist

Run this checklist once after setup:

1. Stream runs for 5 to 10 minutes without camera read failures.
2. FPS overlay remains stable near your selected profile target.
3. Snapshot files are created in artifacts/snapshots.
4. If USE_VOICE=true, TTS response is audible without freezing video.
5. Gesture recognition still functions if voice backend is disabled.

## Environment Variables

- CAMERA_BACKEND: auto, gstreamer, index
- CAMERA_INDEX: camera device index (default 0)
- CAMERA_FPS: target FPS (default 30)
- FRAME_WIDTH: capture width (default 1280)
- FRAME_HEIGHT: capture height (default 720)
- GST_PROFILE: balanced, low_latency, high_detail
- GST_PIPELINE: custom override pipeline string (optional)
- GESTURE_BACKEND: auto, mediapipe_tasks, rules
- GESTURE_MODEL_PATH: path to MediaPipe Tasks gesture model asset
- MIN_DETECTION_CONF: MediaPipe detection confidence
- MIN_TRACKING_CONF: MediaPipe tracking confidence
- GESTURE_MIN_CONF: minimum score for gesture acceptance
- GESTURE_SMOOTHING_WINDOW: number of frames for majority smoothing
- GESTURE_COOLDOWN: minimum seconds between gesture triggers
- SNAPSHOT_DIR: output directory for snapshots
- USE_VOICE: true/false for voice module enablement
- TTS_BACKEND: piper, pyttsx3, espeak, auto
- PIPER_BINARY: piper executable name/path
- PIPER_MODEL_PATH: local Piper voice model path

## Notes for Jetson

- Use CAMERA_BACKEND=gstreamer and GST_PROFILE=balanced for IMX219 on Jetson Orin Nano.
- If the GStreamer path fails, set CAMERA_BACKEND=index for a fallback path.
- For offline voice, set TTS_BACKEND=piper and provide PIPER_MODEL_PATH.

## Roadmap

1. Stabilize camera + gesture loop at target FPS.
2. Add command-level assistant state machine combining gesture and voice.
3. Replace placeholder media/volume actions with real system integrations.
4. Add metrics (latency, trigger precision, false positives) and demo scenarios.
5. Package as a one-command showcase for portfolio demonstrations.
