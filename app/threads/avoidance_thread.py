"""QThread for obstacle avoidance state machine with GPT-4o advisor."""

import time
import threading
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

from app.drone.avoidance import AvoidanceState, AvoidanceAction
from app.vision.gpt_advisor import GPTAdvisor


class AvoidanceThread(QThread):
    """Runs the obstacle avoidance state machine in a loop."""

    state_changed = pyqtSignal(str, str)  # state_name, action_name
    decision_made = pyqtSignal(str)  # action description for logging

    # GPT log signals
    gpt_sent = pyqtSignal(str)
    gpt_received = pyqtSignal(str)
    gpt_error = pyqtSignal(str)

    # Command display on video feed
    command_display = pyqtSignal(str)  # direction + velocity text for overlay

    def __init__(self, avoidance, mavlink_comm, parent=None):
        super().__init__(parent)
        self.avoidance = avoidance
        self.mavlink = mavlink_comm
        self._running = False
        self._enabled = False
        self._forward_distance = None
        self._last_state = None
        self._pre_avoidance_mode = None  # mode before avoidance took over

        # GPT advisor
        self._gpt_advisor = GPTAdvisor()
        self._gpt_pending = False  # True while GPT call is in-flight
        self._latest_frame = None  # latest RGB frame for GPT snapshot
        self._avoidance_mode = "auto"  # "auto" or "gpt"
        self._distances = None  # {center, left, right} from depth model
        self._avoidance_in_mission = True  # run avoidance even during AUTO
        self._current_flight_mode = "UNKNOWN"  # tracked from telemetry

    def set_enabled(self, enabled):
        self._enabled = enabled
        if not enabled:
            self._restore_mode()
            self.avoidance.reset()
            self._gpt_pending = False
            print("[AVOIDANCE] Disabled — state reset to IDLE")
        else:
            print(f"[AVOIDANCE] Enabled — mode={self._avoidance_mode}")

    def set_avoidance_mode(self, mode):
        """Set avoidance decision mode: 'auto' or 'gpt'."""
        self._avoidance_mode = mode
        print(f"[AVOIDANCE] Mode set to: {mode}")

    def set_avoidance_during_mission(self, enabled):
        """Whether to run avoidance while drone is in AUTO mission mode."""
        self._avoidance_in_mission = enabled
        print(f"[AVOIDANCE] Avoidance during mission: {'ON' if enabled else 'OFF'}")

    def update_current_mode(self, mode):
        """Track the current flight mode (from telemetry)."""
        self._current_flight_mode = mode

    def _switch_to_guided(self):
        """Force-switch drone to GUIDED mode for velocity control."""
        if not self.mavlink.connected:
            return
        current_mode = self._current_flight_mode or "UNKNOWN"
        if current_mode != "GUIDED":
            self._pre_avoidance_mode = current_mode
        print(f"[AVOIDANCE] Mode: {current_mode} -> GUIDED (forcing switch...)")

        # Send set_mode multiple times to ensure ArduPilot accepts it
        for attempt in range(5):
            self.mavlink.set_mode("GUIDED")
            # Also send hover (zero velocity) to stop forward motion immediately
            self.mavlink.hover()
            time.sleep(0.2)

            # Verify mode changed
            telem = self.mavlink.get_telemetry() or {}
            if telem.get("mode") == "GUIDED":
                print(f"[AVOIDANCE] GUIDED confirmed after {attempt+1} attempt(s)")
                return

        print(f"[AVOIDANCE] WARNING: GUIDED mode not confirmed after 5 attempts")

    def _restore_mode(self):
        """Restore the flight mode that was active before avoidance."""
        if not self._pre_avoidance_mode or not self.mavlink.connected:
            return
        prev_mode = self._pre_avoidance_mode
        print(f"[AVOIDANCE] Mode: GUIDED -> {prev_mode} (restoring...)")

        for attempt in range(5):
            self.mavlink.set_mode(prev_mode)
            time.sleep(0.2)
            telem = self.mavlink.get_telemetry() or {}
            if telem.get("mode") == prev_mode:
                print(f"[AVOIDANCE] {prev_mode} confirmed after {attempt+1} attempt(s)")
                break

        # If we were in AUTO (mission), re-send mission_start to resume
        if prev_mode == "AUTO":
            time.sleep(0.3)
            self.mavlink.mission_start()
            print(f"[AVOIDANCE] Mission resumed (MISSION_START sent)")
        self._pre_avoidance_mode = None

    def update_distance(self, distance):
        """Called from camera thread signal to update forward distance."""
        self._forward_distance = distance

    def update_altitude(self, altitude):
        """Called from drone telemetry to update altitude."""
        self.avoidance.update_altitude(altitude)

    def update_frame(self, rgb_frame):
        """Store latest RGB frame for GPT snapshot."""
        self._latest_frame = rgb_frame.copy()

    def update_distances(self, distances):
        """Store latest left/center/right distances from depth model."""
        self._distances = distances

    # ── GPT Worker ────────────────────────────────────────

    def _call_gpt(self, telemetry, distance, distances):
        """Worker function — runs GPT call in a background thread."""
        try:
            import math
            L = (distances or {}).get("left", 0) or 0
            R = (distances or {}).get("right", 0) or 0
            prompt_summary = (
                f"Telemetry -> GPT-4o  |  "
                f"fwd={distance:.2f}m L={L:.2f}m R={R:.2f}m  "
                f"alt={telemetry.get('altitude', 0):.1f}m  "
                f"hdg={telemetry.get('heading', 0)} deg"
            )
            self.gpt_sent.emit(prompt_summary)

            cmd = self._gpt_advisor.ask(
                telemetry, distance, distances,
                threshold=self.avoidance.DISTANCE_THRESHOLD,
            )

            if cmd:
                vx, vy, vz = cmd["vx"], cmd["vy"], cmd["vz"]
                dur = cmd["duration"]
                direction = cmd["direction"]
                reasoning = cmd["reasoning"]

                # Set override on the state machine
                self.avoidance.set_gpt_command(vx, vy, vz, dur)

                recv_msg = (
                    f"{direction} for {dur:.1f}s  "
                    f"vel=({vx:.2f}, {vy:.2f}, {vz:.2f})  "
                    f"| {reasoning}"
                )
                self.gpt_received.emit(recv_msg)

                print(
                    f"[GPT] OK {direction} vx={vx:.2f} vy={vy:.2f} vz={vz:.2f} "
                    f"dur={dur:.1f}s | {reasoning}"
                )
            else:
                self.gpt_error.emit("GPT returned empty response — using fallback")
                print("[GPT] Empty response — fallback to random")

        except Exception as e:
            error_msg = str(e)[:100]
            self.gpt_error.emit(error_msg)
            print(f"[GPT] ERROR: {error_msg} — fallback to random")

        finally:
            self._gpt_pending = False

    # ── Main Loop ─────────────────────────────────────────

    def run(self):
        self._running = True
        last_mode_check = 0.0
        while self._running:
            if not self._enabled or not self.mavlink.connected:
                self.msleep(100)
                continue

            # If drone is in AUTO (mission) and user disabled mission-avoidance,
            # stay idle so mission runs uninterrupted
            if (self._current_flight_mode == "AUTO"
                    and not self._avoidance_in_mission
                    and self.avoidance.state == AvoidanceState.IDLE):
                self.msleep(100)
                continue

            state, action, velocity = self.avoidance.update(self._forward_distance)

            # Periodically verify drone is still in GUIDED mode during avoidance
            # AUTO mode or RC FLTMODE can fight back and override GUIDED
            if state not in (AvoidanceState.IDLE,) and self._pre_avoidance_mode is not None:
                now_ts = time.time()
                if now_ts - last_mode_check > 0.5:  # check every 500ms
                    last_mode_check = now_ts
                    if self._current_flight_mode != "GUIDED":
                        self.mavlink.set_mode("GUIDED")
                        self.mavlink.hover()
                        print(f"[AVOIDANCE] Mode drift: {self._current_flight_mode} -> re-forcing GUIDED + hover")

            # Emit state changes
            state_str = state.value
            action_str = action.value
            if state != self._last_state:
                self.state_changed.emit(state_str, action_str)
                dist_str = f"{self._forward_distance:.2f}m" if self._forward_distance else "N/A"
                timestamp = time.strftime("%H:%M:%S")

                if state == AvoidanceState.OBSTACLE_DETECTED:
                    self._switch_to_guided()
                    msg = f"[{timestamp}] Obstacle detected at {dist_str} — stopping!"
                    self.decision_made.emit(msg)
                    print(f"[AVOIDANCE] *** OBSTACLE DETECTED *** dist={dist_str} threshold={self.avoidance.DISTANCE_THRESHOLD}m")

                elif state == AvoidanceState.HOVERING:
                    print(f"[AVOIDANCE] HOVERING -- stabilizing for {self.avoidance.HOVER_STABILIZE_TIME}s, drone must stop completely")
                    if self._avoidance_mode == "gpt":
                        print(f"[AVOIDANCE] -> querying GPT-4o (waiting for response)...")
                        # Launch GPT call in background thread
                        if not self._gpt_pending:
                            self._gpt_pending = True
                            telemetry = self.mavlink.get_telemetry() or {}
                            gpt_thread = threading.Thread(
                                target=self._call_gpt,
                                args=(telemetry, self._forward_distance or 0, self._distances),
                                daemon=True,
                            )
                            gpt_thread.start()
                    else:
                        # Auto mode — smart logic-based decision using spatial depth
                        dist = self._forward_distance or 0
                        alt = self.avoidance._current_altitude
                        attempt = self.avoidance._attempt_count
                        dists = self._distances or {}
                        action, vx, vy, vz, dur = self.avoidance.decide_action_smart(dist, dists)
                        self.avoidance.current_action = action
                        self.avoidance.set_gpt_command(vx, vy, vz, dur)
                        L = dists.get("left", 0) or 0
                        R = dists.get("right", 0) or 0
                        print(
                            f"[AVOIDANCE] AUTO: {action.value} "
                            f"vel=({vx:.2f},{vy:.2f},{vz:.2f}) dur={dur:.1f}s "
                            f"| fwd={dist:.2f}m L={L:.2f}m R={R:.2f}m alt={alt:.1f}m attempt={attempt}"
                        )

                elif state == AvoidanceState.EXECUTING:
                    vx, vy, vz = velocity
                    gpt_dur = self.avoidance._gpt_duration
                    dur = gpt_dur if gpt_dur else self.avoidance.MANEUVER_DURATION
                    action_str = self.avoidance.current_action.value

                    # Build human-readable direction
                    dirs = []
                    if vx < -0.05: dirs.append("BACKWARD")
                    elif vx > 0.05: dirs.append("FORWARD")
                    if vy < -0.05: dirs.append("LEFT")
                    elif vy > 0.05: dirs.append("RIGHT")
                    if vz < -0.05: dirs.append("UP")
                    elif vz > 0.05: dirs.append("DOWN")
                    direction = " + ".join(dirs) if dirs else "HOVER"

                    msg = f"[{timestamp}] {direction}: vel=({vx:.2f},{vy:.2f},{vz:.2f}) {dur:.1f}s (dist={dist_str})"
                    self.decision_made.emit(msg)
                    self.command_display.emit(
                        f">> {direction}\nvel=({vx:.2f}, {vy:.2f}, {vz:.2f})  {dur:.1f}s"
                    )
                    print(f"[AVOIDANCE] EXECUTING: {direction} vel=({vx:.2f}, {vy:.2f}, {vz:.2f}) | duration={dur:.1f}s")

                elif state == AvoidanceState.COMPLETED:
                    self.command_display.emit("")
                    print(f"[AVOIDANCE] MANEUVER COMPLETE -- checking if obstacle cleared (dist={dist_str})")

                elif state == AvoidanceState.CLEARANCE:
                    vx, vy, vz = velocity
                    self.command_display.emit(
                        f">> CLEARANCE (flying past obstacle)\nvel=({vx:.2f}, {vy:.2f}, {vz:.2f})  {self.avoidance.CLEARANCE_DURATION:.0f}s"
                    )
                    msg = f"[{timestamp}] CLEARANCE: flying forward to pass obstacle ({self.avoidance.CLEARANCE_DURATION:.0f}s)"
                    self.decision_made.emit(msg)
                    print(f"[AVOIDANCE] CLEARANCE: flying forward vel=({vx:.2f}, {vy:.2f}, {vz:.2f}) for {self.avoidance.CLEARANCE_DURATION}s")

                elif state == AvoidanceState.IDLE:
                    self._restore_mode()
                    self.command_display.emit("")
                    print(f"[AVOIDANCE] IDLE -- obstacle cleared + passed, resuming normal flight")

                self._last_state = state

            # Send velocity commands when avoiding
            vx, vy, vz = velocity
            if state in (AvoidanceState.OBSTACLE_DETECTED, AvoidanceState.HOVERING,
                         AvoidanceState.COMPLETED):
                self.mavlink.hover()
            elif state in (AvoidanceState.EXECUTING, AvoidanceState.CLEARANCE):
                self.mavlink.send_velocity(vx, vy, vz)
                d = f"{self._forward_distance:.2f}m" if self._forward_distance else "N/A"
                phase = "CLEAR" if state == AvoidanceState.CLEARANCE else "AVOID"
                print(
                    f"[AVOIDANCE] >> {phase} vel=({vx:.2f}, {vy:.2f}, {vz:.2f}) dist={d}", end="\r"
                )

            self.msleep(50)  # 20 Hz

    def stop(self):
        self._running = False
        self.wait(2000)
