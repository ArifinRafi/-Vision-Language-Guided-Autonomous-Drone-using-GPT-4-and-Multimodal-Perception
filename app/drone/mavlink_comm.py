"""MAVLink communication module for ArduPilot drones."""

import time
import threading
from pymavlink import mavutil


class MAVLinkComm:
    """Handles MAVLink connection, telemetry, and command sending."""

    def __init__(self):
        self.connection = None
        self.connected = False
        self._lock = threading.Lock()
        self.target_system = 1
        self.target_component = 1

    def connect(self, connection_string="udp:127.0.0.1:14550"):
        """Establish MAVLink connection."""
        try:
            self.connection = mavutil.mavlink_connection(connection_string)
            self.connection.wait_heartbeat(timeout=10)
            self.target_system = self.connection.target_system
            self.target_component = self.connection.target_component
            self.connected = True
            return True
        except Exception as e:
            self.connected = False
            raise ConnectionError(f"Failed to connect: {e}")

    def disconnect(self):
        """Close the MAVLink connection."""
        if self.connection:
            self.connection.close()
        self.connected = False

    def get_telemetry(self):
        """Poll and return latest telemetry data."""
        if not self.connected:
            return None

        data = {
            "altitude": 0.0,
            "groundspeed": 0.0,
            "airspeed": 0.0,
            "heading": 0,
            "battery_voltage": 0.0,
            "battery_remaining": -1,
            "gps_fix": 0,
            "gps_satellites": 0,
            "lat": 0.0,
            "lon": 0.0,
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": 0.0,
            "mode": "UNKNOWN",
            "armed": False,
        }

        with self._lock:
            # Read all available messages
            while True:
                msg = self.connection.recv_match(blocking=False)
                if msg is None:
                    break
                msg_type = msg.get_type()

                if msg_type == "HEARTBEAT":
                    data["mode"] = mavutil.mode_string_v10(msg)
                    data["armed"] = (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0

                elif msg_type == "GLOBAL_POSITION_INT":
                    data["altitude"] = msg.relative_alt / 1000.0
                    data["lat"] = msg.lat / 1e7
                    data["lon"] = msg.lon / 1e7

                elif msg_type == "VFR_HUD":
                    data["groundspeed"] = msg.groundspeed
                    data["airspeed"] = msg.airspeed
                    data["heading"] = msg.heading
                    data["altitude"] = msg.alt

                elif msg_type == "SYS_STATUS":
                    data["battery_voltage"] = msg.voltage_battery / 1000.0
                    data["battery_remaining"] = msg.battery_remaining

                elif msg_type == "ATTITUDE":
                    data["roll"] = msg.roll
                    data["pitch"] = msg.pitch
                    data["yaw"] = msg.yaw

                elif msg_type == "GPS_RAW_INT":
                    data["gps_fix"] = msg.fix_type
                    data["gps_satellites"] = msg.satellites_visible

        return data

    def send_manual_control(self, x=0, y=0, z=500, r=0):
        """Send MANUAL_CONTROL message.

        Args:
            x: forward/backward (-1000 to 1000), positive = forward
            y: left/right (-1000 to 1000), positive = right
            z: throttle (0 to 1000), 500 = mid
            r: yaw (-1000 to 1000), positive = clockwise
        """
        if not self.connected:
            return
        with self._lock:
            self.connection.mav.manual_control_send(
                self.target_system,
                int(x), int(y), int(z), int(r),
                0  # buttons
            )

    def send_velocity(self, vx=0, vy=0, vz=0):
        """Send velocity command in body frame (NED).

        Args:
            vx: forward velocity m/s (positive = forward)
            vy: right velocity m/s (positive = right)
            vz: down velocity m/s (positive = down, negative = up)
        """
        if not self.connected:
            return
        with self._lock:
            self.connection.mav.set_position_target_local_ned_send(
                0,  # time_boot_ms
                self.target_system,
                self.target_component,
                mavutil.mavlink.MAV_FRAME_BODY_NED,
                0b0000111111000111,  # type_mask: only velocities
                0, 0, 0,  # position (ignored)
                vx, vy, vz,  # velocity
                0, 0, 0,  # acceleration (ignored)
                0, 0  # yaw, yaw_rate (ignored)
            )

    def set_mode(self, mode_name):
        """Set flight mode by name (e.g., 'GUIDED', 'LOITER', 'STABILIZE')."""
        if not self.connected:
            return False
        mode_id = self.connection.mode_mapping().get(mode_name)
        if mode_id is None:
            return False
        with self._lock:
            self.connection.set_mode(mode_id)
        return True

    def arm(self):
        """Arm the drone."""
        if not self.connected:
            return
        with self._lock:
            self.connection.arducopter_arm()

    def disarm(self):
        """Disarm the drone."""
        if not self.connected:
            return
        with self._lock:
            self.connection.arducopter_disarm()

    def hover(self):
        """Command the drone to hover in place (zero velocity)."""
        self.send_velocity(0, 0, 0)
