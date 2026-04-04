"""Manual control panel with keyboard controls and speed input."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QGroupBox, QSpinBox, QPushButton, QLineEdit, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


class ControlPanel(QWidget):
    """Manual control panel with connection settings and keyboard control."""

    connect_requested = pyqtSignal(str)  # connection string
    disconnect_requested = pyqtSignal()
    arm_requested = pyqtSignal()
    disarm_requested = pyqtSignal()
    mode_change_requested = pyqtSignal(str)
    avoidance_toggled = pyqtSignal(bool)
    camera_changed = pyqtSignal(int)  # camera device id

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Camera group
        cam_group = QGroupBox("Camera")
        cam_group.setStyleSheet(self._group_style())
        cam_layout = QHBoxLayout(cam_group)
        cam_layout.addWidget(QLabel("Device:"))
        self._cam_combo = QComboBox()
        self._cam_combo.setStyleSheet("background: #2a2a2a; color: #eee; padding: 4px;")
        for i in range(4):
            self._cam_combo.addItem(f"Camera {i}", i)
        self._cam_combo.currentIndexChanged.connect(
            lambda: self.camera_changed.emit(self._cam_combo.currentData())
        )
        cam_layout.addWidget(self._cam_combo)
        layout.addWidget(cam_group)

        # Connection group
        conn_group = QGroupBox("Connection")
        conn_group.setStyleSheet(self._group_style())
        conn_layout = QHBoxLayout(conn_group)

        self._conn_input = QLineEdit("udp:127.0.0.1:14550")
        self._conn_input.setStyleSheet("background: #2a2a2a; color: #eee; border: 1px solid #555; padding: 4px;")
        conn_layout.addWidget(self._conn_input)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setStyleSheet(self._btn_style("#2196F3"))
        self._connect_btn.clicked.connect(self._on_connect)
        conn_layout.addWidget(self._connect_btn)

        self._disconnect_btn = QPushButton("Disconnect")
        self._disconnect_btn.setStyleSheet(self._btn_style("#666"))
        self._disconnect_btn.clicked.connect(self.disconnect_requested.emit)
        self._disconnect_btn.setEnabled(False)
        conn_layout.addWidget(self._disconnect_btn)

        layout.addWidget(conn_group)

        # Arm/Mode group
        cmd_group = QGroupBox("Commands")
        cmd_group.setStyleSheet(self._group_style())
        cmd_layout = QHBoxLayout(cmd_group)

        self._arm_btn = QPushButton("ARM")
        self._arm_btn.setStyleSheet(self._btn_style("#f44336"))
        self._arm_btn.clicked.connect(self.arm_requested.emit)
        cmd_layout.addWidget(self._arm_btn)

        self._disarm_btn = QPushButton("DISARM")
        self._disarm_btn.setStyleSheet(self._btn_style("#4CAF50"))
        self._disarm_btn.clicked.connect(self.disarm_requested.emit)
        cmd_layout.addWidget(self._disarm_btn)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["STABILIZE", "GUIDED", "LOITER", "ALT_HOLD", "LAND", "RTL"])
        self._mode_combo.setStyleSheet("background: #2a2a2a; color: #eee; padding: 4px;")
        cmd_layout.addWidget(self._mode_combo)

        self._mode_btn = QPushButton("Set Mode")
        self._mode_btn.setStyleSheet(self._btn_style("#FF9800"))
        self._mode_btn.clicked.connect(lambda: self.mode_change_requested.emit(self._mode_combo.currentText()))
        cmd_layout.addWidget(self._mode_btn)

        layout.addWidget(cmd_group)

        # Speed + Manual Control group
        ctrl_group = QGroupBox("Manual Control (WASD + Q/E + R/F)")
        ctrl_group.setStyleSheet(self._group_style())
        ctrl_layout = QVBoxLayout(ctrl_group)

        # Speed input
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Speed (%):"))
        self._speed_spin = QSpinBox()
        self._speed_spin.setRange(0, 100)
        self._speed_spin.setValue(30)
        self._speed_spin.setStyleSheet("background: #2a2a2a; color: #eee; padding: 4px;")
        speed_layout.addWidget(self._speed_spin)
        ctrl_layout.addLayout(speed_layout)

        # Key indicator
        self._key_label = QLabel("Keys: --")
        self._key_label.setFont(QFont("Consolas", 11))
        self._key_label.setAlignment(Qt.AlignCenter)
        self._key_label.setStyleSheet("color: #0f0; background: #111; padding: 8px; border: 1px solid #333;")
        ctrl_layout.addWidget(self._key_label)

        # Key legend
        legend = QLabel(
            "W/S: Forward/Back  |  A/D: Left/Right\n"
            "Q/E: Yaw Left/Right  |  R/F: Up/Down"
        )
        legend.setStyleSheet("color: #888; font-size: 10px;")
        legend.setAlignment(Qt.AlignCenter)
        ctrl_layout.addWidget(legend)

        layout.addWidget(ctrl_group)

        # Avoidance toggle
        avoid_group = QGroupBox("Obstacle Avoidance")
        avoid_group.setStyleSheet(self._group_style())
        avoid_layout = QHBoxLayout(avoid_group)

        self._avoid_btn = QPushButton("Enable Avoidance")
        self._avoid_btn.setCheckable(True)
        self._avoid_btn.setStyleSheet(self._btn_style("#9C27B0"))
        self._avoid_btn.toggled.connect(self._on_avoidance_toggle)
        avoid_layout.addWidget(self._avoid_btn)

        layout.addWidget(avoid_group)
        layout.addStretch()

        # Track pressed keys
        self._pressed_keys = set()

    def get_speed(self):
        """Return speed as fraction 0.0 - 1.0."""
        return self._speed_spin.value() / 100.0

    def get_manual_control_values(self):
        """Return (x, y, z, r) based on currently pressed keys and speed.

        Returns values in -1000 to 1000 range for x, y, r and 0-1000 for z.
        """
        speed = self._speed_spin.value() * 10  # 0-1000 range

        x = 0  # forward/backward
        y = 0  # left/right
        z = 500  # throttle mid
        r = 0  # yaw

        if Qt.Key_W in self._pressed_keys:
            x = speed
        if Qt.Key_S in self._pressed_keys:
            x = -speed
        if Qt.Key_A in self._pressed_keys:
            y = -speed
        if Qt.Key_D in self._pressed_keys:
            y = speed
        if Qt.Key_Q in self._pressed_keys:
            r = -speed
        if Qt.Key_E in self._pressed_keys:
            r = speed
        if Qt.Key_R in self._pressed_keys:
            z = 500 + speed // 2
        if Qt.Key_F in self._pressed_keys:
            z = 500 - speed // 2

        return (x, y, z, r)

    def handle_key_press(self, key):
        self._pressed_keys.add(key)
        self._update_key_display()

    def handle_key_release(self, key):
        self._pressed_keys.discard(key)
        self._update_key_display()

    def _update_key_display(self):
        if not self._pressed_keys:
            self._key_label.setText("Keys: --")
            return
        key_names = {
            Qt.Key_W: "W↑", Qt.Key_S: "S↓", Qt.Key_A: "A←", Qt.Key_D: "D→",
            Qt.Key_Q: "Q⟲", Qt.Key_E: "E⟳", Qt.Key_R: "R▲", Qt.Key_F: "F▼"
        }
        active = [key_names.get(k, "") for k in self._pressed_keys if k in key_names]
        self._key_label.setText("Keys: " + " ".join(active) if active else "Keys: --")

    def set_connected(self, connected):
        self._connect_btn.setEnabled(not connected)
        self._disconnect_btn.setEnabled(connected)
        if connected:
            self._connect_btn.setText("Connected")
            self._connect_btn.setStyleSheet(self._btn_style("#4CAF50"))
        else:
            self._connect_btn.setText("Connect")
            self._connect_btn.setStyleSheet(self._btn_style("#2196F3"))

    def _on_connect(self):
        self.connect_requested.emit(self._conn_input.text().strip())

    def _on_avoidance_toggle(self, checked):
        self._avoid_btn.setText("Avoidance ON" if checked else "Enable Avoidance")
        self.avoidance_toggled.emit(checked)

    @staticmethod
    def _group_style():
        return """
            QGroupBox {
                font-weight: bold; font-size: 11px; color: #0af;
                border: 1px solid #333; border-radius: 4px;
                margin-top: 8px; padding-top: 14px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
        """

    @staticmethod
    def _btn_style(color):
        return f"""
            QPushButton {{
                background-color: {color}; color: white; border: none;
                padding: 6px 14px; border-radius: 3px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {color}; opacity: 0.8; }}
            QPushButton:pressed {{ background-color: #333; }}
            QPushButton:disabled {{ background-color: #555; color: #999; }}
        """
