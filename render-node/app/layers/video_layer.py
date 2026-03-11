from __future__ import annotations
import time
from typing import Any, Optional, Dict
import numpy as np
import av
import wgpu
import logging

logger = logging.getLogger(__name__)

class VideoLayer:
    """
    VideoLayer using PyAV to decode frames and upload to wgpu textures.
    Supports MP4/H.264, MOV, and HAP (via ffmpeg codec).
    """
    def __init__(self, device: wgpu.GPUDevice, path: str, layer_id: str):
        self.device = device
        self.path = path
        self.layer_id = layer_id
        
        try:
            self.container = av.open(path)
            self.stream = self.container.streams.video[0]
            self.width = self.stream.width
            self.height = self.stream.height
            self.fps = float(self.stream.average_rate)
            self.duration_sec = float(self.stream.duration * self.stream.time_base)
            logger.info(f"[video-layer] Opened {path}: {self.width}x{self.height} @ {self.fps} FPS")
        except Exception as e:
            logger.error(f"[video-layer] Failed to open {path}: {e}")
            raise

        self.texture: Optional[wgpu.GPUTexture] = None
        self._create_texture()
        
        self.current_frame_rgba: Optional[bytes] = None
        self.pts_ms: float = 0.0
        self.is_playing = False
        self.loop = True
        self.opacity = 1.0
        self.transform = {"x": 0.0, "y": 0.0, "scale_x": 1.0, "scale_y": 1.0, "rotation": 0.0}
        self.blend_mode = "normal"
        self.z_index = 0
        
    def _create_texture(self):
        self.texture = self.device.create_texture(
            size=(self.width, self.height, 1),
            usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
            format=wgpu.TextureFormat.rgba8unorm,
        )

    def seek(self, pts_seconds: float):
        """Seek to a presentation timestamp (seconds)."""
        target_ts = int(pts_seconds / float(self.stream.time_base))
        self.container.seek(target_ts, any_frame=False, backward=True, stream=self.stream)
        self.pts_ms = pts_seconds * 1000.0

    def decode_next_frame(self) -> bool:
        """
        Decodes the next frame from the stream.
        Returns True if a frame was successfully decoded.
        """
        try:
            for packet in self.container.demux(self.stream):
                for frame in packet.decode():
                    # Convert to RGBA
                    img_data = frame.to_ndarray(format="rgba")
                    self.current_frame_rgba = img_data.tobytes()
                    if frame.pts is not None:
                        self.pts_ms = float(frame.pts * self.stream.time_base * 1000.0)
                    return True
        except (av.EOFError, StopIteration):
            if self.loop:
                self.seek(0)
                return self.decode_next_frame()
            return False
        except Exception as e:
            logger.error(f"[video-layer] Decode error: {e}")
            return False
        return False

    def upload_to_gpu(self):
        """Upload current frame data to the wgpu texture."""
        if self.current_frame_rgba and self.texture:
            self.device.queue.write_texture(
                {"texture": self.texture, "origin": (0, 0, 0)},
                self.current_frame_rgba,
                {"bytes_per_row": self.width * 4, "rows_per_image": self.height},
                (self.width, self.height, 1),
            )

    def set_opacity(self, opacity: float):
        self.opacity = max(0.0, min(1.0, opacity))

    def set_transform(self, x: float, y: float, scale_x: float, scale_y: float, rotation: float):
        self.transform = {
            "x": x,
            "y": y,
            "scale_x": scale_x,
            "scale_y": scale_y,
            "rotation": rotation
        }
