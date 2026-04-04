"""Depth Anything V2 Small model for monocular depth estimation."""

import numpy as np
import torch
from transformers import pipeline


class DepthEstimator:
    """Wraps Depth Anything V2 Small for depth map inference."""

    MODEL_ID = "depth-anything/Depth-Anything-V2-Small-hf"

    def __init__(self, device=None):
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        self.pipe = None
        self.depth_scale = 1.0  # Calibration scale factor for metric depth

    def load(self):
        """Load the depth estimation pipeline."""
        self.pipe = pipeline(
            "depth-estimation",
            model=self.MODEL_ID,
            device=self.device,
        )

    # Resolution to run inference at — smaller = faster, less accurate
    INFERENCE_SIZE = (320, 240)  # (width, height)

    def estimate(self, rgb_frame):
        """Run depth estimation on an RGB frame.

        Args:
            rgb_frame: numpy array (H, W, 3) in RGB format, uint8.

        Returns:
            depth_map: numpy array (H, W) with relative depth values (float32).
            center_distance: estimated distance to center region in meters.
        """
        if self.pipe is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        import cv2
        from PIL import Image

        # Downscale for faster inference
        small = cv2.resize(rgb_frame, self.INFERENCE_SIZE)
        image = Image.fromarray(small)

        result = self.pipe(image)
        depth_map = np.array(result["depth"], dtype=np.float32)

        # Resize depth map to match input frame
        if depth_map.shape[:2] != rgb_frame.shape[:2]:
            import cv2
            depth_map = cv2.resize(depth_map, (rgb_frame.shape[1], rgb_frame.shape[0]))

        # Normalize to 0-1 range
        d_min = depth_map.min()
        d_max = depth_map.max()
        if d_max - d_min > 0:
            depth_normalized = (depth_map - d_min) / (d_max - d_min)
        else:
            depth_normalized = np.zeros_like(depth_map)

        # Extract center region distance
        center_distance = self._estimate_center_distance(depth_normalized)

        return depth_normalized, center_distance

    def _estimate_center_distance(self, depth_normalized):
        """Estimate distance from center region of the depth map.

        Uses the center 20% of the frame. Higher depth values = farther away
        in Depth Anything output, so we invert for distance.

        Returns approximate distance in meters.
        """
        h, w = depth_normalized.shape
        cy, cx = h // 2, w // 2
        rh, rw = h // 10, w // 10  # 20% region

        center_region = depth_normalized[cy - rh:cy + rh, cx - rw:cx + rw]
        if center_region.size == 0:
            return None

        # Depth Anything: higher values = closer (disparity-like)
        # Convert to distance: distance ~ scale / disparity
        mean_depth = center_region.mean()
        if mean_depth < 0.01:
            return 10.0  # Very far

        # Approximate metric conversion
        # This is a rough heuristic — tune depth_scale for your camera/setup
        distance = self.depth_scale / (mean_depth + 0.01)
        return float(np.clip(distance, 0.1, 20.0))

    def colorize_depth(self, depth_normalized):
        """Convert normalized depth map to a colorized RGB image for display.

        Args:
            depth_normalized: (H, W) float32 array in [0, 1].

        Returns:
            colorized: (H, W, 3) uint8 RGB image.
        """
        import cv2
        depth_uint8 = (depth_normalized * 255).astype(np.uint8)
        colorized = cv2.applyColorMap(depth_uint8, cv2.COLORMAP_INFERNO)
        return cv2.cvtColor(colorized, cv2.COLOR_BGR2RGB)
