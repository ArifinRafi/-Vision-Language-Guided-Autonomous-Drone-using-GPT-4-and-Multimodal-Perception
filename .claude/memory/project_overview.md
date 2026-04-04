---
name: Project Overview
description: VLM-Drone Stage 1 — PyQt5 drone control app with Depth Anything V2 obstacle avoidance
type: project
---

Stage 1 is complete. A PyQt5 app that:
- Controls ArduPilot drone via pymavlink over UDP (udp:127.0.0.1:14550)
- Shows live RGB video (USB webcam, OpenCV) with decision overlay
- Runs Depth Anything V2 Small (HuggingFace) for monocular depth estimation
- Autonomous obstacle avoidance: if object < 1m → stop → hover → random maneuver (backward/up/down)
- Manual control via WASD+QE+RF keys with configurable speed %
- Displays full telemetry: altitude, speed, heading, battery, GPS, attitude, mode, armed

**Why:** Stage 2 features will be added later (not yet defined by user).
**How to apply:** Any future features should extend the existing thread/widget architecture without breaking Stage 1.

File structure:
- main.py — entry point
- app/main_window.py — orchestration
- app/drone/mavlink_comm.py — MAVLink comms
- app/drone/avoidance.py — state machine (IDLE→DETECTED→HOVERING→EXECUTING→COMPLETED)
- app/vision/camera.py — OpenCV capture (320x240, buffer=1)
- app/vision/depth_model.py — Depth Anything V2 Small, inference at 320x240
- app/threads/ — DroneThread, CameraThread (30fps display / 3fps depth), AvoidanceThread
- app/widgets/ — VideoWidget, DepthWidget, StatusPanel, ControlPanel, AvoidanceLog
