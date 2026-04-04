"""QThread for obstacle avoidance state machine."""

import time
from PyQt5.QtCore import QThread, pyqtSignal

from app.drone.avoidance import AvoidanceState, AvoidanceAction


class AvoidanceThread(QThread):
    """Runs the obstacle avoidance state machine in a loop."""

    state_changed = pyqtSignal(str, str)  # state_name, action_name
    decision_made = pyqtSignal(str)  # action description for logging

    def __init__(self, avoidance, mavlink_comm, parent=None):
        super().__init__(parent)
        self.avoidance = avoidance
        self.mavlink = mavlink_comm
        self._running = False
        self._enabled = False
        self._forward_distance = None
        self._last_state = None

    def set_enabled(self, enabled):
        self._enabled = enabled
        if not enabled:
            self.avoidance.reset()

    def update_distance(self, distance):
        """Called from camera thread signal to update forward distance."""
        self._forward_distance = distance

    def update_altitude(self, altitude):
        """Called from drone telemetry to update altitude."""
        self.avoidance.update_altitude(altitude)

    def run(self):
        self._running = True
        while self._running:
            if not self._enabled or not self.mavlink.connected:
                self.msleep(100)
                continue

            state, action, velocity = self.avoidance.update(self._forward_distance)

            # Emit state changes
            state_str = state.value
            action_str = action.value
            if state != self._last_state:
                self.state_changed.emit(state_str, action_str)
                if state == AvoidanceState.EXECUTING:
                    timestamp = time.strftime("%H:%M:%S")
                    self.decision_made.emit(
                        f"[{timestamp}] Avoiding obstacle: {action_str} "
                        f"(dist={self._forward_distance:.2f}m)"
                        if self._forward_distance else
                        f"[{timestamp}] Avoiding obstacle: {action_str}"
                    )
                elif state == AvoidanceState.OBSTACLE_DETECTED:
                    timestamp = time.strftime("%H:%M:%S")
                    self.decision_made.emit(
                        f"[{timestamp}] Obstacle detected at "
                        f"{self._forward_distance:.2f}m — stopping!"
                        if self._forward_distance else
                        f"[{timestamp}] Obstacle detected — stopping!"
                    )
                self._last_state = state

            # Send velocity commands when avoiding
            vx, vy, vz = velocity
            if state in (AvoidanceState.OBSTACLE_DETECTED, AvoidanceState.HOVERING,
                         AvoidanceState.COMPLETED):
                self.mavlink.hover()
            elif state == AvoidanceState.EXECUTING:
                self.mavlink.send_velocity(vx, vy, vz)

            self.msleep(50)  # 20 Hz

    def stop(self):
        self._running = False
        self.wait(2000)
