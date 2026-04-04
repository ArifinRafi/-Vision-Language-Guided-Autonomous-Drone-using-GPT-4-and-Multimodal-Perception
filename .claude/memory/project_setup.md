---
name: Setup Notes
description: Local environment and dependency setup details for VLM-Drone
type: project
---

- Project path: E:\VLM-Drone\
- Virtual env: E:\VLM-Drone\venv\ (Python 3.9.13)
- Key packages: PyQt5 5.15.11, pymavlink 2.4.49, opencv-python 4.13, torch 2.8.0, transformers 4.57.6, pillow 11.3.0, numpy 2.0.2
- Depth model cached at: C:\Users\Arifin Rafi\.cache\huggingface\hub\models--depth-anything--Depth-Anything-V2-Small-hf
- Drone: ArduPilot, UDP connection (default udp:127.0.0.1:14550)
- Camera: USB webcam, device_id=0 (selector in UI for 0-3), capture at 320x240

**Why:** Reference for recreating the environment on a new device.
**How to apply:** On a new device run: python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt
