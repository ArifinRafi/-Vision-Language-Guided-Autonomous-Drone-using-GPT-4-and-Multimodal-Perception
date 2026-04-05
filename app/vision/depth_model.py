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
        # Calibration: metric_distance = depth_scale / raw_disparity
        # To calibrate: place an object at a known distance (e.g. 1m),
        # read the raw disparity from the CLI, then set:
        #   depth_scale = known_distance * raw_disparity
        self.depth_scale = 2.0

    def load(self):
        """Load the depth estimation pipeline."""
        self.pipe = pipeline(
            "depth-estimation",
            model=self.MODEL_ID,
            device=self.device,
        )
        print("[DEPTH] Model loaded on", self.device)

    # Resolution to run inference at — smaller = faster, less accurate
    INFERENCE_SIZE = (320, 240)  # (width, height)

    def estimate(self, rgb_frame):
        """Run depth estimation on an RGB frame.

        Args:
            rgb_frame: numpy array (H, W, 3) in RGB format, uint8.

        Returns:
            depth_normalized: numpy array (H, W) normalized 0-1 (float32).
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

        # Use raw predicted_depth (disparity) for distance estimation
        raw_disparity = result["predicted_depth"].numpy().squeeze()

        # Resize to match input frame
        if raw_disparity.shape[:2] != rgb_frame.shape[:2]:
            raw_disparity = cv2.resize(raw_disparity, (rgb_frame.shape[1], rgb_frame.shape[0]))

        # Normalize to 0-1 for visualization
        d_min = raw_disparity.min()
        d_max = raw_disparity.max()
        if d_max - d_min > 0:
            depth_normalized = (raw_disparity - d_min) / (d_max - d_min)
        else:
            depth_normalized = np.zeros_like(raw_disparity)

        # Extract regional distances using raw disparity
        center_distance = self._estimate_region_distance(raw_disparity, "center")
        left_distance = self._estimate_region_distance(raw_disparity, "left")
        right_distance = self._estimate_region_distance(raw_disparity, "right")

        distances = {
            "center": center_distance,
            "left": left_distance,
            "right": right_distance,
        }

        return depth_normalized, center_distance, distances

    def _estimate_region_distance(self, raw_disparity, region="center"):
        """Estimate distance to the closest object in a region.

        Regions:
            center: center 20% of frame
            left:   left third, middle vertical band
            right:  right third, middle vertical band

        Uses 75th percentile of disparity (focuses on closest objects).
        Returns approximate distance in meters.
        """
        h, w = raw_disparity.shape
        cy = h // 2
        rh = h // 5  # vertical band height (40% of frame)

        if region == "center":
            cx = w // 2
            rw = w // 10
            roi = raw_disparity[cy - rh:cy + rh, cx - rw:cx + rw]
        elif region == "left":
            # Left third: columns 0 to w/3
            x_start = 0
            x_end = w // 3
            roi = raw_disparity[cy - rh:cy + rh, x_start:x_end]
        elif region == "right":
            # Right third: columns 2w/3 to w
            x_start = 2 * w // 3
            x_end = w
            roi = raw_disparity[cy - rh:cy + rh, x_start:x_end]
        else:
            return None

        if roi.size == 0:
            return None

        disp_p75 = float(np.percentile(roi, 75))
        if disp_p75 < 0.01:
            return 20.0

        distance = self.depth_scale / disp_p75
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
