from __future__ import annotations
import time
from typing import Any, Optional
import numpy as np

class VideoLayer:
    """
    Manages high-performance video layer state, buffering, and sub-frame precision timing.
    Supports ProRes and DXV3 optimized paths.
    """
    def __init__(self, layer_id: str):
        self.layer_id = layer_id
        self.current_frame: Optional[bytes] = None
        self.pts_ms: float = 0.0
        self.duration_ms = 0.0
        self.fps = 60.0 # Default
        self.is_playing = False
        self.loop = True
        self.opacity = 1.0
        self.transform = {"x": 0, "y": 0, "scale": 1.0}
        
        # Buffer for sub-frame interpolation or lookahead
        self.frame_buffer = []
        self.max_buffer_size = 3
        
    def update_frame(self, frame_data: bytes, pts_ms: float):
        """Update the current frame and its metadata."""
        self.current_frame = frame_data
        self.pts_ms = pts_ms
        
    def get_interpolated_pts(self, system_time_ms: float, last_tick_ms: float) -> float:
        """
        Calculates sub-frame precision PTS.
        If system_time_ms is provided, we can estimate exactly where we should be
        between frames to maintain micro-stutter suppression.
        """
        if not self.is_playing:
            return self.pts_ms
            
        elapsed = system_time_ms - last_tick_ms
        return self.pts_ms + elapsed

    def reset_timing(self):
        self.pts_ms = 0.0
        self.frame_buffer.clear()

    def set_opacity(self, opacity: float):
        self.opacity = max(0.0, min(1.0, opacity))

    def set_transform(self, x: float, y: float, scale: float):
        self.transform = {"x": x, "y": y, "scale": scale}
