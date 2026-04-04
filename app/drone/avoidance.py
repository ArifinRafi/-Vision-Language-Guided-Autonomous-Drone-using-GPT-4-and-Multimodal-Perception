"""Obstacle avoidance state machine."""

import enum
import random
import time


class AvoidanceState(enum.Enum):
    IDLE = "IDLE"
    OBSTACLE_DETECTED = "OBSTACLE_DETECTED"
    HOVERING = "HOVERING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"


class AvoidanceAction(enum.Enum):
    NONE = "NONE"
    BACKWARD = "BACKWARD"
    UP = "UP"
    DOWN = "DOWN"


class ObstacleAvoidance:
    """State machine for obstacle avoidance decisions."""

    DISTANCE_THRESHOLD = 1.0  # meters
    HOVER_STABILIZE_TIME = 1.0  # seconds
    MANEUVER_DURATION = 2.0  # seconds
    MANEUVER_SPEED = 0.5  # m/s
    MIN_ALTITUDE_FOR_DOWN = 2.0  # meters — don't go down if below this

    def __init__(self):
        self.state = AvoidanceState.IDLE
        self.current_action = AvoidanceAction.NONE
        self._state_enter_time = 0.0
        self._current_altitude = 0.0

    def update_altitude(self, altitude):
        """Update the current altitude for decision making."""
        self._current_altitude = altitude

    def decide_action(self):
        """Choose a random avoidance action based on current conditions."""
        choices = [AvoidanceAction.BACKWARD, AvoidanceAction.UP]
        if self._current_altitude > self.MIN_ALTITUDE_FOR_DOWN:
            choices.append(AvoidanceAction.DOWN)
        return random.choice(choices)

    def get_velocity_for_action(self, action):
        """Return (vx, vy, vz) for the given avoidance action."""
        speed = self.MANEUVER_SPEED
        if action == AvoidanceAction.BACKWARD:
            return (-speed, 0, 0)
        elif action == AvoidanceAction.UP:
            return (0, 0, -speed)  # NED: negative z = up
        elif action == AvoidanceAction.DOWN:
            return (0, 0, speed)  # NED: positive z = down
        return (0, 0, 0)

    def update(self, forward_distance):
        """Update the state machine. Returns (state, action, velocity_cmd).

        Args:
            forward_distance: estimated distance to forward object in meters.
                             None if no measurement available.

        Returns:
            tuple: (state, action, (vx, vy, vz))
        """
        now = time.time()

        if self.state == AvoidanceState.IDLE:
            if forward_distance is not None and forward_distance < self.DISTANCE_THRESHOLD:
                self.state = AvoidanceState.OBSTACLE_DETECTED
                self._state_enter_time = now
                self.current_action = AvoidanceAction.NONE
            return (self.state, self.current_action, (0, 0, 0))

        elif self.state == AvoidanceState.OBSTACLE_DETECTED:
            # Stop all movement
            self.state = AvoidanceState.HOVERING
            self._state_enter_time = now
            return (self.state, AvoidanceAction.NONE, (0, 0, 0))

        elif self.state == AvoidanceState.HOVERING:
            elapsed = now - self._state_enter_time
            if elapsed >= self.HOVER_STABILIZE_TIME:
                # Make decision
                self.current_action = self.decide_action()
                self.state = AvoidanceState.EXECUTING
                self._state_enter_time = now
            return (self.state, self.current_action, (0, 0, 0))

        elif self.state == AvoidanceState.EXECUTING:
            elapsed = now - self._state_enter_time
            vel = self.get_velocity_for_action(self.current_action)
            if elapsed >= self.MANEUVER_DURATION:
                self.state = AvoidanceState.COMPLETED
                self._state_enter_time = now
                return (self.state, self.current_action, (0, 0, 0))
            return (self.state, self.current_action, vel)

        elif self.state == AvoidanceState.COMPLETED:
            # Check if obstacle is cleared
            if forward_distance is None or forward_distance >= self.DISTANCE_THRESHOLD:
                self.state = AvoidanceState.IDLE
                self.current_action = AvoidanceAction.NONE
            else:
                # Still blocked, hover and decide again
                self.state = AvoidanceState.HOVERING
                self._state_enter_time = now
            return (self.state, self.current_action, (0, 0, 0))

        return (self.state, self.current_action, (0, 0, 0))

    def reset(self):
        """Reset state machine to IDLE."""
        self.state = AvoidanceState.IDLE
        self.current_action = AvoidanceAction.NONE
