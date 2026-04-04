# VLM-Drone — Claude Code Context

## Project
PyQt5 desktop app for controlling an ArduPilot drone via MAVLink with real-time depth-based obstacle avoidance using Depth Anything V2 Small.

## Setup (new device)
```bash
python -m venv venv
venv\Scripts\activate        # Windows CMD
# or: .\venv\Scripts\Activate.ps1  (PowerShell)
pip install -r requirements.txt
python main.py
```

## Run
```bash
python main.py
```

## Architecture
- `app/drone/mavlink_comm.py` — MAVLink connection & commands (ArduPilot, UDP)
- `app/drone/avoidance.py` — Obstacle avoidance state machine
- `app/vision/camera.py` — OpenCV USB webcam (320x240, buffer=1)
- `app/vision/depth_model.py` — Depth Anything V2 Small inference (HuggingFace)
- `app/threads/` — DroneThread (20Hz telemetry), CameraThread (30fps/3fps depth), AvoidanceThread
- `app/widgets/` — VideoWidget, DepthWidget, StatusPanel, ControlPanel, AvoidanceLog
- `app/main_window.py` — MainWindow orchestration
- `main.py` — Entry point

## Key Defaults
- MAVLink: `udp:127.0.0.1:14550`
- Camera: device_id=0, 320x240 (switchable 0-3 in UI)
- Depth inference: 320x240 input, 3 FPS on CPU
- Obstacle threshold: 1.0 m (see `avoidance.py: DISTANCE_THRESHOLD`)
- Avoidance maneuver speed: 0.5 m/s, duration: 2s

## Memory
Session memory is in `.claude/memory/`. To activate on a new device:
```
copy .claude\memory\* "C:\Users\<username>\.claude\projects\<project-slug>\memory\"
```
The project slug matches the project path with `\` replaced by `-` and drive colon removed,
e.g. `E:\VLM-Drone` → `E--VLM-Drone`.

## Stage
Currently **Stage 1** complete. Stage 2 features TBD by user.
