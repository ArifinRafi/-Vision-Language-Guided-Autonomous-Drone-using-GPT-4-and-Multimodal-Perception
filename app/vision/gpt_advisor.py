"""GPT-4o advisor for intelligent obstacle avoidance decisions."""

import os
import json
import math


class GPTAdvisor:
    """Sends camera snapshot + telemetry to GPT-4o Vision and parses avoidance commands."""

    MODEL = "gpt-4o"

    SYSTEM_PROMPT = (
        "You are an autonomous drone obstacle avoidance system. "
        "You receive current flight telemetry and depth sensor readings. "
        "An obstacle has been detected ahead. Your job is to decide the best "
        "avoidance maneuver so the drone can safely navigate around the obstacle.\n\n"
        "Respond ONLY with a JSON object — no markdown, no extra text:\n"
        '{"vx": float, "vy": float, "vz": float, "duration": float, "reasoning": "brief explanation"}\n\n'
        "Velocity is in NED body frame:\n"
        "- vx: forward(+) / backward(-), range -1.0 to 1.0 m/s\n"
        "- vy: right(+) / left(-), range -1.0 to 1.0 m/s\n"
        "- vz: down(+) / up(-), range -1.0 to 1.0 m/s\n"
        "- duration: how long to execute in seconds, range 1.0 to 5.0\n\n"
        "Guidelines:\n"
        "- If left distance > right distance, move left (vy negative).\n"
        "- If right distance > left distance, move right (vy positive).\n"
        "- If both sides are blocked, move backward (vx negative).\n"
        "- Prefer lateral moves over altitude changes when possible.\n"
        "- If altitude is low (< 2m), do NOT move down (vz must be <= 0).\n"
        "- Keep velocities conservative (0.3 to 0.8 m/s).\n"
        "- Keep reasoning under 20 words."
    )

    def __init__(self):
        self._client = None

    def _get_client(self):
        """Lazy-init OpenAI client."""
        if self._client is None:
            from openai import OpenAI
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY environment variable not set")
            self._client = OpenAI(api_key=api_key)
        return self._client

    def _build_user_prompt(self, telemetry, distance, distances, threshold):
        """Build the text portion of the user message."""
        alt = telemetry.get("altitude", 0.0)
        heading = telemetry.get("heading", 0)
        roll = math.degrees(telemetry.get("roll", 0.0))
        pitch = math.degrees(telemetry.get("pitch", 0.0))
        yaw = math.degrees(telemetry.get("yaw", 0.0))
        speed = telemetry.get("groundspeed", 0.0)
        mode = telemetry.get("mode", "UNKNOWN")
        dist_left = (distances or {}).get("left", 20.0) or 20.0
        dist_right = (distances or {}).get("right", 20.0) or 20.0

        return (
            f"Obstacle detected at {distance:.2f}m (threshold: {threshold}m).\n\n"
            f"Depth sensor readings:\n"
            f"- Center distance: {distance:.2f}m\n"
            f"- Left distance: {dist_left:.2f}m\n"
            f"- Right distance: {dist_right:.2f}m\n\n"
            f"Current telemetry:\n"
            f"- Altitude: {alt:.1f}m\n"
            f"- Heading: {heading} deg\n"
            f"- Roll: {roll:.1f} deg | Pitch: {pitch:.1f} deg | Yaw: {yaw:.1f} deg\n"
            f"- Ground Speed: {speed:.1f} m/s\n"
            f"- Mode: {mode}\n\n"
            f"Decide the avoidance maneuver based on the depth readings and telemetry."
        )

    def ask(self, telemetry, distance, distances=None, threshold=1.0):
        """Send telemetry + depth data to GPT-4o and return avoidance command.

        Args:
            telemetry: dict from MAVLinkComm.get_telemetry()
            distance: forward center distance in meters
            distances: dict with 'left', 'center', 'right' distances
            threshold: obstacle threshold in meters

        Returns:
            dict: {"vx", "vy", "vz", "duration", "reasoning"} or None on failure
        """
        client = self._get_client()
        user_text = self._build_user_prompt(telemetry, distance, distances, threshold)

        prompt_summary = (
            f"dist={distance:.2f}m alt={telemetry.get('altitude', 0):.1f}m "
            f"hdg={telemetry.get('heading', 0)}° "
            f"roll={math.degrees(telemetry.get('roll', 0)):.0f}° "
            f"pitch={math.degrees(telemetry.get('pitch', 0)):.0f}° "
            f"yaw={math.degrees(telemetry.get('yaw', 0)):.0f}°"
        )

        print(f"[GPT] Sending snapshot + telemetry -> GPT-4o ({prompt_summary})")

        response = client.chat.completions.create(
            model=self.MODEL,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            max_tokens=200,
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        msg = response.choices[0].message
        raw = msg.content
        refusal = getattr(msg, "refusal", None)

        if refusal:
            print(f"[GPT] Refused: {refusal}")
            return None

        if raw is None or not raw.strip():
            print(f"[GPT] Empty response")
            return None

        raw = raw.strip()
        print(f"[GPT] Raw response: {raw}")

        # Parse JSON — handle markdown code fences
        text = raw
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            text = text.rsplit("```", 1)[0]
            text = text.strip()

        # Check if it looks like JSON before parsing
        if not text.startswith("{"):
            print(f"[GPT] Non-JSON response: {text[:80]}")
            return None

        cmd = json.loads(text)

        # Validate required keys
        for key in ("vx", "vy", "vz", "duration"):
            if key not in cmd:
                print(f"[GPT] Missing key '{key}' in response")
                return None

        # Clamp values
        cmd["vx"] = max(-1.0, min(1.0, float(cmd["vx"])))
        cmd["vy"] = max(-1.0, min(1.0, float(cmd["vy"])))
        cmd["vz"] = max(-1.0, min(1.0, float(cmd["vz"])))
        cmd["duration"] = max(1.0, min(5.0, float(cmd["duration"])))
        cmd["reasoning"] = str(cmd.get("reasoning", ""))

        # Direction label
        dirs = []
        if cmd["vx"] < -0.1:
            dirs.append("BACKWARD")
        elif cmd["vx"] > 0.1:
            dirs.append("FORWARD")
        if cmd["vy"] < -0.1:
            dirs.append("LEFT")
        elif cmd["vy"] > 0.1:
            dirs.append("RIGHT")
        if cmd["vz"] < -0.1:
            dirs.append("UP")
        elif cmd["vz"] > 0.1:
            dirs.append("DOWN")
        cmd["direction"] = "-".join(dirs) if dirs else "HOVER"

        print(
            f"[GPT] >> {cmd['direction']} "
            f"vx={cmd['vx']:.2f} vy={cmd['vy']:.2f} vz={cmd['vz']:.2f} "
            f"dur={cmd['duration']:.1f}s | {cmd['reasoning']}"
        )

        return cmd
