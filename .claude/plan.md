# VLM-Drone: PyQt Drone Control App with Depth-Based Obstacle Avoidance

## Context
Build a PyQt5 desktop application that controls an ArduPilot drone via pymavlink over UDP, displays live RGB video with depth estimation using Depth Anything V2 Small, and performs fully autonomous obstacle avoidance when objects are detected within 1 meter.

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    MainWindow (PyQt5)                │
│ ┌──────────────┐ ┌──────────────┐ ┌───────────────┐ │
│ │  RGB Video    │ │ Depth Map    │ │ Drone Status  │ │
│ │  + Decision   │ │  Window      │ │ Panel         │ │
│ │  Overlay      │ │              │ │ (alt,speed,..)│ │
│ ├──────────────┤ ├──────────────┤ ├───────────────┤ │
│ │ Manual Ctrl   │ │ Avoidance    │ │ Connection    │ │
│ │ (WASD + speed)│ │ Status/Log   │ │ Settings      │ │
│ └──────────────┘ └──────────────┘ └───────────────┘ │
└─────────────────────────────────────────────────────┘
```

## File Structure

```
E:\VLM-Drone\
├── main.py                  # Entry point
├── requirements.txt         # Dependencies
├── app/
│   ├── __init__.py
│   ├── main_window.py       # MainWindow layout & orchestration
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── video_widget.py  # RGB video display with decision overlay
│   │   ├── depth_widget.py  # Depth map display
│   │   ├── control_panel.py # Manual control (WASD keys + speed input)
│   │   ├── status_panel.py  # Drone telemetry display
│   │   └── avoidance_log.py # Avoidance decisions log
│   ├── drone/
│   │   ├── __init__.py
│   │   ├── mavlink_comm.py  # MAVLink connection & command sending
│   │   └── avoidance.py     # Obstacle avoidance logic (state machine)
│   ├── vision/
│   │   ├── __init__.py
│   │   ├── camera.py        # Camera capture thread (OpenCV)
│   │   └── depth_model.py   # Depth Anything V2 Small inference
│   └── threads/
│       ├── __init__.py
│       ├── drone_thread.py  # QThread for MAVLink telemetry polling
│       ├── camera_thread.py # QThread for camera + depth inference
│       └── avoidance_thread.py # QThread for avoidance state machine
```

## Key Components

### 1. MAVLink Communication (`drone/mavlink_comm.py`)
- Connect via `mavutil.mavlink_connection('udp:127.0.0.1:14550')`
- Configurable UDP address/port in UI
- Send manual control commands: `MANUAL_CONTROL` message (x=forward/back, y=left/right, z=throttle, r=yaw)
- Receive telemetry: `HEARTBEAT`, `GLOBAL_POSITION_INT`, `ATTITUDE`, `VFR_HUD`, `SYS_STATUS`
- Mode switching: GUIDED mode for autonomous, LOITER for hover-hold
- Arm/disarm commands

### 2. Manual Control (`widgets/control_panel.py`)
- Speed input (slider or spinbox, 0-100% range mapped to RC values)
- Keyboard WASD for direction: W=forward, S=backward, A=left, D=right
- Q/E for yaw left/right, R/F for up/down
- Speed value from user input scales all movement commands
- Visual indicator showing active direction

### 3. Camera + Depth Pipeline (`vision/`)
- **camera.py**: OpenCV `VideoCapture(0)`, configurable resolution (640x480 default)
- **depth_model.py**:
  - Load Depth Anything V2 Small via `transformers` (HuggingFace) or `torch.hub`
  - Model: `depth-anything/Depth-Anything-V2-Small`
  - Input: RGB frame → Output: depth map (relative depth)
  - Convert relative depth to approximate metric depth using scaling factor (configurable)
  - Extract center-region depth for forward obstacle distance

### 4. Obstacle Avoidance State Machine (`drone/avoidance.py`)
States:
- `IDLE` → monitoring depth, manual control active
- `OBSTACLE_DETECTED` → object < 1m detected, stop movement
- `HOVERING` → stabilized hover, preparing decision
- `EXECUTING` → performing avoidance maneuver (random: backward, up, or down)
- `COMPLETED` → maneuver done, return to IDLE

Logic:
1. Continuously check center depth from depth model
2. If depth < 1m threshold → transition to OBSTACLE_DETECTED
3. Send zero velocity commands (hover in place)
4. Wait ~1 second for stabilization
5. Randomly choose: backward, up, or down (weighted by current altitude — don't go down if too low)
6. Execute maneuver for fixed duration/distance
7. Re-check depth → if clear, return to IDLE; else repeat

### 5. UI Layout (`main_window.py`)
- Left: RGB video (640x480) with overlay text showing current decision
- Right-top: Depth map (colorized)
- Right-bottom: Drone status panel (altitude, speed, heading, battery, GPS, mode, armed state)
- Bottom-left: Manual control panel with speed input
- Bottom-right: Avoidance decision log (timestamped list)

### 6. Threading Model
- **CameraThread (QThread)**: captures frames, runs depth inference, emits `frame_ready(rgb, depth, distance)` signal
- **DroneThread (QThread)**: polls MAVLink messages, emits `telemetry_updated(data)` signal
- **AvoidanceThread (QThread)**: runs state machine, reads depth distance, sends commands via MAVLink, emits `decision_made(action)` signal
- Main thread: UI only, receives signals and updates widgets

## Dependencies (`requirements.txt`)
```
PyQt5>=5.15
pymavlink>=2.4.40
opencv-python>=4.8
torch>=2.0
transformers>=4.35
numpy
```

## Implementation Order
1. Project skeleton + `requirements.txt` + `main.py`
2. MAVLink communication module (connect, send commands, receive telemetry)
3. Drone thread + status panel (verify connection works)
4. Camera capture thread + RGB video widget
5. Depth model integration + depth widget
6. Manual control panel (keyboard + speed input)
7. Avoidance state machine + avoidance thread
8. Decision overlay on RGB video + avoidance log widget
9. Wire everything together in MainWindow
10. Testing & polish

## Verification
1. Run `python main.py` — UI should launch with all panels
2. Connect to ArduPilot SITL (`sim_vehicle.py -v ArduCopter`) on UDP 14550
3. Verify telemetry displays in status panel
4. Verify camera feed shows in RGB window
5. Verify depth map renders in depth window
6. Test manual control with WASD keys
7. Place object close to camera → verify avoidance triggers, decision overlays on video
