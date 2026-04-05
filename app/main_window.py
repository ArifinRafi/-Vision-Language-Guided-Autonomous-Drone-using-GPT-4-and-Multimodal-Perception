"""Main application window — orchestrates all components."""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QMessageBox, QStatusBar, QApplication
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QColor


class ModelLoaderThread(QThread):
    """Loads the depth model in background without blocking the UI."""
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, depth_estimator, parent=None):
        super().__init__(parent)
        self.depth_estimator = depth_estimator

    def run(self):
        try:
            self.depth_estimator.load()
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

from app.drone.mavlink_comm import MAVLinkComm
from app.drone.avoidance import ObstacleAvoidance, AvoidanceState
from app.vision.camera import Camera
from app.vision.depth_model import DepthEstimator
from app.threads.drone_thread import DroneThread
from app.threads.camera_thread import CameraThread
from app.threads.avoidance_thread import AvoidanceThread
from app.widgets.video_widget import VideoWidget
from app.widgets.depth_widget import DepthWidget
from app.widgets.status_panel import StatusPanel
from app.widgets.control_panel import ControlPanel
from app.widgets.avoidance_log import AvoidanceLog
from app.widgets.gpt_log import GPTLog


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VLM-Drone Control")
        self.setMinimumSize(1280, 800)
        self.setStyleSheet("background-color: #1e1e1e; color: #eee;")

        # Core components
        self._mavlink = MAVLinkComm()
        self._avoidance = ObstacleAvoidance()
        self._camera = Camera(device_id=0)
        self._depth_estimator = DepthEstimator()

        # Threads
        self._drone_thread = DroneThread(self._mavlink)
        self._camera_thread = CameraThread(self._camera, self._depth_estimator)
        self._avoidance_thread = AvoidanceThread(self._avoidance, self._mavlink)

        # Latest telemetry
        self._last_telemetry = {}

        self._build_ui()
        self._connect_signals()
        self._setup_manual_control_timer()

        self._load_depth_model()
        self._start_camera()

    # ── UI Layout ──────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # Left column: video + controls
        left = QVBoxLayout()
        self._video_widget = VideoWidget("RGB Video")
        left.addWidget(self._video_widget, stretch=3)

        self._control_panel = ControlPanel()
        left.addWidget(self._control_panel, stretch=2)

        # Right column: depth + status + avoidance log
        right = QVBoxLayout()
        self._depth_widget = DepthWidget()
        right.addWidget(self._depth_widget, stretch=2)

        self._status_panel = StatusPanel()
        right.addWidget(self._status_panel, stretch=2)

        self._avoidance_log = AvoidanceLog()
        right.addWidget(self._avoidance_log, stretch=1)

        self._gpt_log = GPTLog()
        right.addWidget(self._gpt_log, stretch=1)

        main_layout.addLayout(left, stretch=3)
        main_layout.addLayout(right, stretch=2)

        # Status bar
        self._status_bar = QStatusBar()
        self._status_bar.setStyleSheet("color: #888; font-size: 11px;")
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready — not connected")

    # ── Signal Wiring ──────────────────────────────────────

    def _connect_signals(self):
        # Control panel
        self._control_panel.connect_requested.connect(self._on_connect)
        self._control_panel.disconnect_requested.connect(self._on_disconnect)
        self._control_panel.arm_requested.connect(self._mavlink.arm)
        self._control_panel.disarm_requested.connect(self._mavlink.disarm)
        self._control_panel.mode_change_requested.connect(self._mavlink.set_mode)
        self._control_panel.avoidance_toggled.connect(self._on_avoidance_toggle)
        self._control_panel.avoidance_mode_changed.connect(self._avoidance_thread.set_avoidance_mode)
        self._control_panel.camera_changed.connect(self._on_camera_changed)

        # Drone thread
        self._drone_thread.telemetry_updated.connect(self._on_telemetry)
        self._drone_thread.connection_status.connect(self._on_connection_status)

        # Camera thread
        self._camera_thread.frame_ready.connect(self._on_frame_ready)
        self._camera_thread.error_occurred.connect(
            lambda e: self._status_bar.showMessage(f"Camera error: {e}")
        )

        # Avoidance thread
        self._avoidance_thread.state_changed.connect(self._on_avoidance_state)
        self._avoidance_thread.decision_made.connect(self._avoidance_log.add_log_entry)

        # GPT advisor signals
        self._avoidance_thread.gpt_sent.connect(self._gpt_log.add_sent)
        self._avoidance_thread.gpt_received.connect(self._gpt_log.add_received)
        self._avoidance_thread.gpt_error.connect(self._gpt_log.add_error)

        # Command overlay on video
        self._avoidance_thread.command_display.connect(self._video_widget.set_command_text)

    # ── Initialization ─────────────────────────────────────

    def _load_depth_model(self):
        self._status_bar.showMessage("Loading Depth Anything V2 Small model in background...")
        self._model_loader = ModelLoaderThread(self._depth_estimator)
        self._model_loader.finished.connect(
            lambda: self._status_bar.showMessage("Depth model loaded — depth estimation active")
        )
        self._model_loader.error.connect(
            lambda e: self._status_bar.showMessage(f"Depth model failed: {e}")
        )
        self._model_loader.start()

    def _start_camera(self):
        try:
            self._camera.open()
            self._camera_thread.start()
            self._status_bar.showMessage("Camera started")
        except Exception as e:
            self._status_bar.showMessage(f"Camera error: {e}")

    def _on_camera_changed(self, device_id):
        """Switch to a different camera device."""
        self._camera_thread.stop()
        self._camera.release()
        self._camera.device_id = device_id
        try:
            self._camera.open()
            self._camera_thread = CameraThread(self._camera, self._depth_estimator)
            self._camera_thread.frame_ready.connect(self._on_frame_ready)
            self._camera_thread.error_occurred.connect(
                lambda e: self._status_bar.showMessage(f"Camera error: {e}")
            )
            self._camera_thread.start()
            self._status_bar.showMessage(f"Switched to Camera {device_id}")
        except Exception as e:
            self._status_bar.showMessage(f"Camera {device_id} failed: {e}")

    # ── Connection ─────────────────────────────────────────

    def _on_connect(self, connection_string):
        try:
            self._mavlink.connect(connection_string)
            self._control_panel.set_connected(True)
            self._drone_thread.start()
            self._avoidance_thread.start()
            self._status_bar.showMessage(f"Connected to {connection_string}")
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", str(e))
            self._status_bar.showMessage(f"Connection failed: {e}")

    def _on_disconnect(self):
        self._avoidance_thread.stop()
        self._drone_thread.stop()
        self._mavlink.disconnect()
        self._control_panel.set_connected(False)
        self._status_bar.showMessage("Disconnected")

    def _on_connection_status(self, connected, message):
        if not connected:
            self._status_bar.showMessage(f"Connection issue: {message}")

    # ── Telemetry ──────────────────────────────────────────

    def _on_telemetry(self, data):
        self._last_telemetry = data
        self._status_panel.update_telemetry(data)
        self._avoidance_thread.update_altitude(data.get("altitude", 0))

    # ── Camera / Depth ─────────────────────────────────────

    def _on_frame_ready(self, rgb_frame, depth_colored, center_distance, distances):
        # Update video widget
        self._video_widget.update_frame(rgb_frame)
        self._depth_widget.update_depth(depth_colored)

        # Update distance overlay
        if center_distance is not None:
            L = (distances or {}).get("left", 0) or 0
            R = (distances or {}).get("right", 0) or 0
            self._video_widget.set_distance_text(
                f"Fwd: {center_distance:.2f}m  L: {L:.2f}m  R: {R:.2f}m"
            )
        else:
            self._video_widget.set_distance_text("")

        # Feed distance and frame to avoidance thread
        self._avoidance_thread.update_distance(center_distance)
        self._avoidance_thread.update_distances(distances)
        self._avoidance_thread.update_frame(rgb_frame)

    # ── Avoidance ──────────────────────────────────────────

    def _on_avoidance_toggle(self, enabled):
        self._avoidance_thread.set_enabled(enabled)
        if enabled:
            self._status_bar.showMessage("Obstacle avoidance ENABLED")
        else:
            self._status_bar.showMessage("Obstacle avoidance disabled")
            self._video_widget.clear_overlay()

    def _on_avoidance_state(self, state, action):
        self._avoidance_log.update_state(state, action)

        # Overlay on video
        if state == AvoidanceState.IDLE.value:
            self._video_widget.set_overlay("", QColor(0, 255, 0))
        elif state == AvoidanceState.OBSTACLE_DETECTED.value:
            self._video_widget.set_overlay("OBSTACLE DETECTED — STOPPING", QColor(255, 0, 0))
        elif state == AvoidanceState.HOVERING.value:
            mode = self._avoidance_thread._avoidance_mode
            if mode == "gpt":
                self._video_widget.set_overlay("HOVERING -- QUERYING GPT-4o...", QColor(255, 255, 0))
            else:
                self._video_widget.set_overlay("HOVERING -- DECIDING...", QColor(255, 255, 0))
        elif state == AvoidanceState.EXECUTING.value:
            # Direction is shown by command_display overlay, just show EXECUTING
            self._video_widget.set_overlay("EXECUTING AVOIDANCE", QColor(255, 128, 0))
        elif state == AvoidanceState.COMPLETED.value:
            self._video_widget.set_overlay("MANEUVER COMPLETE", QColor(0, 200, 255))

    # ── Manual Control ─────────────────────────────────────

    def _setup_manual_control_timer(self):
        """Timer to send manual control commands at 10 Hz."""
        self._manual_timer = QTimer()
        self._manual_timer.setInterval(100)
        self._manual_timer.timeout.connect(self._send_manual_control)
        self._manual_timer.start()

    def _send_manual_control(self):
        if not self._mavlink.connected:
            return
        # Don't send manual controls while avoidance is active and not idle
        if (self._avoidance_thread._enabled and
                self._avoidance.state != AvoidanceState.IDLE):
            return
        x, y, z, r = self._control_panel.get_manual_control_values()
        if x != 0 or y != 0 or z != 500 or r != 0:
            self._mavlink.send_manual_control(x, y, z, r)

    def keyPressEvent(self, event):
        if not event.isAutoRepeat():
            self._control_panel.handle_key_press(event.key())
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat():
            self._control_panel.handle_key_release(event.key())
        super().keyReleaseEvent(event)

    # ── Cleanup ────────────────────────────────────────────

    def closeEvent(self, event):
        self._manual_timer.stop()
        self._avoidance_thread.stop()
        self._camera_thread.stop()
        self._drone_thread.stop()
        self._camera.release()
        self._mavlink.disconnect()
        super().closeEvent(event)
