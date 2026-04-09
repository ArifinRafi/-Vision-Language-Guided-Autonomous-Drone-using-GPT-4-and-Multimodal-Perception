# Vision-Language Guided Autonomous Drone (Version 2)

> **VLM-Drone V2** -- A PyQt5-based Ground Control Station (GCS) integrating monocular depth estimation, GPT-4o language-model reasoning, and MAVLink flight control for real-time autonomous obstacle avoidance on ArduPilot drones.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Key Features](#key-features)
4. [Technology Stack](#technology-stack)
5. [Project Structure](#project-structure)
6. [Installation](#installation)
7. [Usage](#usage)
8. [Obstacle Avoidance System](#obstacle-avoidance-system)
9. [GPT-4o Advisor Module](#gpt-4o-advisor-module)
10. [Mission Planning](#mission-planning)
11. [Testing with SITL](#testing-with-sitl)
12. [Results and Observations](#results-and-observations)
13. [Future Work](#future-work)
14. [Author](#author)

---

## Project Overview

This project presents a desktop-based Ground Control Station (GCS) that enables autonomous obstacle avoidance for ArduPilot-based quadrotor drones using Vision-Language Model (VLM) integration. The system combines:

- **Monocular depth estimation** using Depth Anything V2 Small (HuggingFace Transformers) for real-time spatial awareness from a single RGB camera
- **GPT-4o language model reasoning** for intelligent avoidance decision-making based on telemetry and spatial depth data
- **MAVLink protocol communication** via pymavlink for bidirectional drone control and telemetry

The application provides a complete flight control interface with live video feed, depth visualization, telemetry monitoring, manual keyboard control, waypoint mission planning with interactive maps, and two distinct obstacle avoidance modes operating during autonomous missions.

### Problem Statement

Commercial drones operating in GPS-guided autonomous missions lack the ability to detect and avoid unexpected obstacles in their flight path. Traditional obstacle avoidance systems rely on expensive LiDAR or ultrasonic sensors. This project demonstrates that a single low-cost USB camera combined with deep learning-based depth estimation and large language model (LLM) reasoning can provide effective obstacle avoidance for autonomous drone missions.

### Approach

1. A USB webcam captures the forward-facing view at 30 FPS
2. Depth Anything V2 Small performs monocular depth inference at 3 FPS, producing a dense depth map
3. The depth map is analyzed spatially (left, center, right regions) to estimate distances to obstacles
4. When the center distance falls below a configurable threshold (default: 1.0m), the avoidance system activates
5. In **Auto mode**, a logic-based algorithm selects the avoidance direction based on spatial clearance, altitude, and attempt history
6. In **GPT-4o mode**, telemetry and depth readings are sent to OpenAI's GPT-4o model, which returns velocity commands with reasoning
7. The drone executes the avoidance maneuver in GUIDED mode, then enters a clearance phase to fly past the obstacle before resuming the original mission in AUTO mode

---

## System Architecture

```
+------------------+     MAVLink (Serial/UDP)     +------------------+
|                  | <--------------------------> |                  |
|   VLM-Drone V2   |                              |  ArduPilot FC    |
|   (GCS - PyQt5)  |     USB Camera (320x240)     |  (Pixhawk/SITL)  |
|                  | <--------------------------- |                  |
+--------+---------+                              +------------------+
         |
         |  Internal Architecture
         |
    +----+----+--------+--------+--------+
    |         |        |        |        |
    v         v        v        v        v
 Camera    Drone    Avoidance  Mission   GPT-4o
 Thread    Thread   Thread     Thread    Advisor
 (30fps)   (20Hz)   (20Hz)    (async)   (on-demand)
    |         |        |        |        |
    v         v        v        v        v
 Depth     Telemetry  State    Upload/   OpenAI
 Anything  Polling    Machine  Download  API
 V2 Small  (MAVLink)  (6 states)        (JSON)
    |         |        |
    v         v        v
 +------ UI Widgets (PyQt5) ------+
 | RGB Video + Overlay            |
 | Depth Map (Inferno colormap)   |
 | Status Panel (14 fields)       |
 | Control Panel (connection/ARM) |
 | Avoidance Log                  |
 | GPT-4o Advisor Log             |
 | Mission Planner (map + table)  |
 +---------------------------------+
```

### Data Flow

```
Camera Frame (RGB 320x240)
    |
    +---> Display at 30 FPS (VideoWidget)
    |
    +---> Depth Inference at 3 FPS (Depth Anything V2 Small)
              |
              +---> Depth Map Visualization (DepthWidget)
              |
              +---> Spatial Distance Analysis
              |       - Center region (75th percentile)
              |       - Left third
              |       - Right third
              |
              +---> Forward Distance < 1.0m?
                      |
                      YES --> Avoidance State Machine Activated
                              |
                              +---> AUTO --> GUIDED (mode switch, 5 retries)
                              +---> HOVER (1.5s stabilization)
                              +---> Decision (Auto logic OR GPT-4o API)
                              +---> EXECUTE maneuver (2-5 seconds)
                              +---> CLEARANCE (4s forward to pass obstacle)
                              +---> GUIDED --> AUTO (resume mission)
```

---

## Key Features

### Stage 1 -- Core Flight Control
- Live RGB video feed with distance overlay
- Real-time depth map visualization using Depth Anything V2 Small
- Full drone telemetry (altitude, heading, GPS, battery, attitude, motor PWM)
- Manual flight control via keyboard (WASD + QE + RF)
- MAVLink connection via Serial (COM port + baud rate) or UDP
- Dark-themed professional GCS interface

### Stage 2 -- Intelligent Obstacle Avoidance
- **Auto (Logic-Based) Mode**: Spatial depth analysis determines optimal avoidance direction
  - Analyzes left, center, right depth regions
  - Considers altitude, attempt history, and obstacle proximity
  - Escalating strategies: lateral move, backward, climb
- **GPT-4o Advisor Mode**: Sends telemetry + depth readings to GPT-4o
  - Returns JSON velocity commands with reasoning
  - Displayed in dedicated GPT-4o Advisor log panel
  - Automatic fallback to Auto mode on API failure
- **Clearance Phase**: After avoidance, flies forward 4 seconds to pass the obstacle before resuming mission
- **Mode Management**: Robust AUTO/GUIDED switching with verification (5 retries, 500ms drift checks)

### Stage 2 -- Mission Planning
- Interactive Leaflet map (CartoDB dark tiles + ESRI satellite)
- Click-to-add waypoints with numbered markers and polyline path
- Drag markers to reposition waypoints
- Waypoint table with editable lat/lon/alt/command columns
- Supported commands: NAV_TAKEOFF, NAV_WAYPOINT, NAV_LOITER_TIME, NAV_LAND, NAV_RETURN_TO_LAUNCH
- Import/Export Mission Planner .waypoint files
- Offset-based waypoint creation (meters N/E from current position)
- MAVLink mission upload/download protocol implementation
- Live drone position tracking on map
- "Enable avoidance during mission" toggle

### Additional Features
- Serial port auto-detection with refresh
- Persistent OpenAI API key storage (local config, gitignored)
- Motor PWM monitoring (M1-M4) for command verification
- Mission progress tracking (current waypoint display)
- Responsive UI with scrollable control panel
- Two-tab layout: Control + Mission Planner

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| UI Framework | PyQt5 5.15 | Desktop application interface |
| Map Engine | PyQtWebEngine + Leaflet.js | Interactive mission planning map |
| Depth Model | Depth Anything V2 Small (HuggingFace) | Monocular depth estimation |
| Deep Learning | PyTorch 2.6.0 (CPU) | Model inference backend |
| Language Model | OpenAI GPT-4o | Intelligent avoidance reasoning |
| Drone Protocol | pymavlink 2.4.x | MAVLink communication |
| Video Capture | OpenCV 4.13 | USB camera interface |
| Flight Controller | ArduPilot (ArduCopter V4.x) | Drone autopilot firmware |
| Hardware | Pixhawk-compatible FC + SiK telemetry radio | Flight control hardware |

---

## Project Structure

```
VLM-Drone-V2/
|-- main.py                          # Application entry point
|-- requirements.txt                 # Python dependencies
|-- README.md                        # This file
|
|-- app/
|   |-- main_window.py              # Main window with QTabWidget orchestration
|   |
|   |-- drone/                      # MAVLink and flight logic
|   |   |-- mavlink_comm.py         # MAVLink connection, telemetry, commands, mission protocol
|   |   |-- avoidance.py            # 6-state avoidance state machine
|   |   |-- mission.py              # Waypoint dataclass, file parsing, coordinate helpers
|   |
|   |-- vision/                     # Computer vision pipeline
|   |   |-- camera.py               # OpenCV USB camera capture (320x240)
|   |   |-- depth_model.py          # Depth Anything V2 Small inference + spatial analysis
|   |   |-- gpt_advisor.py          # GPT-4o API client with prompt engineering
|   |
|   |-- threads/                    # Background processing threads
|   |   |-- drone_thread.py         # 20 Hz telemetry polling
|   |   |-- camera_thread.py        # 30 FPS display / 3 FPS depth inference
|   |   |-- avoidance_thread.py     # 20 Hz avoidance loop with GPT integration
|   |   |-- mission_thread.py       # Async mission upload/download
|   |
|   |-- widgets/                    # PyQt5 UI components
|       |-- video_widget.py         # RGB video with distance + command overlay
|       |-- depth_widget.py         # Depth map colorized display
|       |-- status_panel.py         # 14-field telemetry display
|       |-- control_panel.py        # Connection, ARM, mode, speed, avoidance config
|       |-- avoidance_log.py        # Avoidance state + decision log
|       |-- gpt_log.py              # GPT-4o send/receive message log
|       |-- mission_planner.py      # Mission tab with map + table + controls
|       |-- map_view.py             # QWebEngineView + QWebChannel bridge
|       |-- map_assets/map.html     # Leaflet map with CartoDB/ESRI tiles
```

**Total: 24 Python files, ~3,600 lines of code**

---

## Installation

### Prerequisites
- Python 3.9 or later
- ArduPilot-compatible drone with MAVLink telemetry (or SITL for simulation)
- USB webcam
- Windows 10/11 (tested)

### Setup

```bash
# Clone the repository
git clone https://github.com/ArifinRafi/VLM-Drone-V1.git
cd VLM-Drone-V1

# Create virtual environment
python -m venv venv

# Activate (Windows CMD)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install CPU-only PyTorch (recommended for Windows compatibility)
pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu --force-reinstall

# Run the application
python main.py
```

### First Run
- The Depth Anything V2 Small model (~100MB) downloads automatically on first launch
- The model is cached at `~/.cache/huggingface/hub/` for subsequent runs

---

## Usage

### Connecting to the Drone

**Serial (Telemetry Radio):**
1. Plug in ground-side telemetry radio via USB
2. Select **Serial** radio button
3. Click refresh to scan COM ports
4. Select the correct COM port (e.g., COM5)
5. Set baud rate to **57600**
6. Click **Connect**

**UDP (SITL or forwarded):**
1. Select **UDP** radio button
2. Enter connection string (e.g., `tcp:127.0.0.1:5763` for SITL)
3. Click **Connect**

### Manual Flight Control

| Key | Action |
|-----|--------|
| W / S | Forward / Backward |
| A / D | Left / Right |
| Q / E | Yaw Left / Yaw Right |
| R / F | Up / Down |

Speed is adjustable via the Speed (%) slider (0-100%).

### Enabling Obstacle Avoidance

1. Select avoidance mode: **Auto (Random)** or **GPT-4o Advisor**
2. Click **Enable Avoidance** (purple button)
3. The system monitors the forward depth continuously
4. When an obstacle is detected within 1.0m, avoidance activates automatically

### GPT-4o Setup
1. Obtain an API key from [platform.openai.com](https://platform.openai.com/api-keys)
2. Paste in the **OpenAI API Key** field
3. Click **Save** (persists locally, not committed to git)

---

## Obstacle Avoidance System

### State Machine (6 States)

```
IDLE --> OBSTACLE_DETECTED --> HOVERING --> EXECUTING --> COMPLETED --> CLEARANCE --> IDLE
                                  ^                          |
                                  |    (still blocked)       |
                                  +--------------------------+
```

| State | Duration | Action |
|-------|----------|--------|
| IDLE | -- | Monitoring forward distance |
| OBSTACLE_DETECTED | instant | Switch to GUIDED mode (5 retries) |
| HOVERING | 1.5s minimum | Stabilize + compute/query avoidance decision |
| EXECUTING | 2-5s | Execute velocity command (avoidance maneuver) |
| COMPLETED | instant | Check if obstacle cleared |
| CLEARANCE | 4s | Fly forward past obstacle before resuming |

### Auto Mode Decision Logic

| Condition | Action | Velocity |
|-----------|--------|----------|
| Left side clear | Move LEFT | (-0.10, -0.40, 0.00) |
| Right side clear | Move RIGHT | (-0.10, 0.40, 0.00) |
| Both clear, left more space | BACKWARD + LEFT | (-0.15, -0.40, 0.00) |
| Both blocked | BACKWARD | (-0.50, 0.00, 0.00) |
| Low altitude + blocked | BACKWARD + UP | (-0.50, 0.00, -0.25) |
| Critical distance (< 0.4m) | Emergency BACKWARD | (-0.75, 0.00, 0.00) |
| 3+ failed attempts | Climb UP | (0.00, 0.00, -0.50) |

### Depth Calibration

The depth model outputs relative disparity values. Distance estimation uses:

```
metric_distance = depth_scale / disparity_p75
```

Where:
- `depth_scale = 2.0` (calibration constant)
- `disparity_p75` = 75th percentile of the center 20% region (focuses on closest objects)
- Spatial analysis divides the frame into left third, center, and right third regions

---

## GPT-4o Advisor Module

When GPT-4o Advisor mode is selected, the system sends telemetry and depth sensor data to OpenAI's GPT-4o model for intelligent decision-making.

### Prompt Design

**System Prompt:**
```
You are an autonomous drone obstacle avoidance system. You receive current
flight telemetry and depth sensor readings. An obstacle has been detected
ahead. Your job is to decide the best avoidance maneuver.

Respond ONLY with JSON:
{"vx": float, "vy": float, "vz": float, "duration": float, "reasoning": "..."}

Velocity is in NED body frame:
- vx: forward(+) / backward(-), range -1.0 to 1.0 m/s
- vy: right(+) / left(-), range -1.0 to 1.0 m/s
- vz: down(+) / up(-), range -1.0 to 1.0 m/s
- duration: 1.0 to 5.0 seconds
```

**User Prompt (per obstacle event):**
```
Obstacle detected at 0.50m (threshold: 1.0m).

Depth sensor readings:
- Center distance: 0.50m
- Left distance: 2.10m
- Right distance: 0.80m

Current telemetry:
- Altitude: 8.5m
- Heading: 236 deg
- Roll: -0.3 deg | Pitch: 1.5 deg | Yaw: -123.8 deg
- Ground Speed: 0.5 m/s
- Mode: GUIDED
```

### Safety Features
- Response validation (JSON parsing, key verification, value clamping)
- 15-second timeout with automatic fallback to Auto mode
- API refusal handling (graceful degradation)
- All GPT commands are velocity-limited to +/-1.0 m/s

---

## Mission Planning

### Workflow: Mission with Obstacle Avoidance

1. **Plan mission** in Mission Planner (external) -- create waypoints, upload to drone
2. **Close Mission Planner**
3. **Open VLM-Drone V2** -- connect to drone via Serial/UDP
4. **Verify mission** (optional) -- Mission Planner tab, click "Download from Drone"
5. **Enable avoidance** -- select mode (Auto/GPT), click Enable Avoidance
6. **Start mission** -- select AUTO mode, Set Mode, ARM
7. **During flight**: obstacle detected at < 1.0m
   - AUTO --> GUIDED (forced, verified)
   - Hover 1.5s, compute avoidance
   - Execute maneuver (2-5s)
   - Clearance phase (4s forward past obstacle)
   - GUIDED --> AUTO (restored, mission_start() re-sent)
8. **Mission completes** -- drone executes final RTL/LAND command

### Interactive Map Features
- Click to add waypoints
- Drag markers to reposition
- Layer switcher (Dark street view / Satellite imagery)
- Live drone position marker
- Polyline connecting waypoints
- Offset-based waypoint creation (meters from current position)
- Import/Export .waypoint files (Mission Planner compatible)

---

## Testing with SITL

The application can be tested without a real drone using ArduPilot's Software-In-The-Loop simulator.

### Setup (via Mission Planner)

1. Open Mission Planner
2. Click **SIMULATION** tab
3. Select **Multirotor** -- SITL downloads and starts
4. VLM-Drone connects via `tcp:127.0.0.1:5763`

### Testing Obstacle Avoidance

Since the depth model runs on the **real USB webcam**, obstacles are triggered by physically placing objects in front of the camera:

- Hold hand ~50cm from webcam -- avoidance triggers
- Block right side, leave left open -- drone chooses LEFT
- Keep blocking -- escalating attempts (lateral, backward, climb)
- The SITL drone **actually moves** in response to velocity commands

---

## Results and Observations

### Depth Estimation Performance
- Inference rate: 3 FPS on CPU (sufficient for obstacle detection)
- Effective detection range: 0.1m to 20.0m
- Center distance accuracy: calibrated to within 10-15% using 75th percentile method
- Spatial analysis (L/C/R) enables directional avoidance decisions

### Avoidance System Performance
- Detection-to-maneuver latency: ~1.5s (hover stabilization)
- GPT-4o response time: 2-5 seconds (network dependent)
- Auto mode response time: < 100ms (local computation)
- Successful obstacle clearance in SITL testing with clearance phase preventing re-encounter

### GPT-4o Decision Quality
- Correct directional decisions based on spatial clearance data
- Consistent velocity magnitudes within safety bounds
- Meaningful reasoning provided with each decision
- Graceful fallback to Auto mode on API failures

---

## Future Work

- Integrate LiDAR/ultrasonic sensors for ground-truth depth validation
- Implement multi-obstacle tracking with individual avoidance paths
- Add visual SLAM for GPS-denied indoor navigation
- Explore on-device language models (e.g., Llama) for offline GPT-like reasoning
- Real-world outdoor flight testing with full mission + avoidance validation
- Implement geofencing and no-fly zone awareness
- Add return-to-sender video streaming for remote monitoring

---

## Author

**Arifin Rafi**
Roboway Technologies

GitHub: [ArifinRafi](https://github.com/ArifinRafi)

---

## License

This project is developed for academic research purposes.
