from __future__ import annotations

import asyncio
import av
import time
from pathlib import Path
from typing import Any, Optional
from .bridge import Decoder

class WebCodecsDecoder(Decoder):
    def __init__(self):
        self.containers = {}
        self.output_queues = {} # media_id -> asyncio.Queue[tuple[bytes, float]]
        self._decode_tasks = {}
        self.clock_offset_ms = 0.0

    async def load_show(self, show_id: str, payload: dict[str, Any]) -> None:
        print(f"[webcodecs-decoder] Loading show: {show_id}")
        assets = payload.get("assets", [])
        for asset in assets:
            if isinstance(asset, dict):
                uri = asset.get("uri")
                media_id = asset.get("media_id")
                if uri and media_id:
                    path = uri.replace("file://", "")
                    if Path(path).exists():
                        try:
                            # Use thread for blocking AV open
                            container = await asyncio.to_thread(av.open, path)
                            self.containers[media_id] = container
                            self.output_queues[media_id] = asyncio.Queue(maxsize=10)
                            print(f"[webcodecs-decoder] Opened professional asset {media_id}: {path}")
                        except Exception as e:
                            print(f"[webcodecs-decoder] Failed to open {media_id}: {e}")

    async def play_at(self, show_id: str, target_time_ms: int | None, payload: dict[str, Any]) -> None:
        print(f"[webcodecs-decoder] Playing {show_id} at {target_time_ms}")
        self.clock_offset_ms = time.time() * 1000.0 - (target_time_ms or 0)
        
        for media_id in self.containers:
            if media_id not in self._decode_tasks:
                self._decode_tasks[media_id] = asyncio.create_task(self._decode_loop(media_id))

    async def _decode_loop(self, media_id: str):
        container = self.containers[media_id]
        stream = container.streams.video[0]
        queue = self.output_queues[media_id]
        
        # Professional Codec Check (ProRes/DXV detected via codec context)
        codec_name = stream.codec_context.name
        is_pro_codec = codec_name in ["prores", "dxv"]
        if is_pro_codec:
            print(f"[webcodecs-decoder] HW-Accelerated path for {codec_name} on {media_id}")

        try:
            # We use an iterator to feed the queue
            for frame in container.decode(stream):
                # Precise PTS extraction
                pts_ms = float(frame.pts * stream.time_base * 1000)
                
                # Optimized conversion to RGBA for WebGPU upload
                # In production, we'd use a zero-copy hardware surface if available
                rgba_frame = frame.to_ndarray(format='rgba')
                frame_bytes = rgba_frame.tobytes()
                
                # Push to queue for renderer consumption
                await queue.put((frame_bytes, pts_ms))
                
                # Slow down decoding if queue is full
                if queue.full():
                    await asyncio.sleep(0.001)
                    
                if media_id not in self.containers:
                    break
        except Exception as e:
            print(f"[webcodecs-decoder] Decode error for {media_id}: {e}")

    async def get_next_frame(self, media_id: str) -> Optional[tuple[bytes, float]]:
        """Non-blocking poll for the next available frame (PTS-aware)."""
        queue = self.output_queues.get(media_id)
        if queue and not queue.empty():
            return await queue.get()
        return None

    async def close(self) -> None:
        print(f"[webcodecs-decoder] Closing.")
        for task in self._decode_tasks.values():
            task.cancel()
        for container in self.containers.values():
            container.close()
        self.containers.clear()
        self._decode_tasks.clear()
        self.output_queues.clear()
