from __future__ import annotations

import asyncio
import av
from pathlib import Path
from typing import Any
from .bridge import Decoder

class WebCodecsDecoder(Decoder):
    def __init__(self):
        self.containers = {}
        self.output_queues = {}
        self._decode_tasks = {}

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
                            container = av.open(path)
                            self.containers[media_id] = container
                            print(f"[webcodecs-decoder] Opened asset {media_id}: {path}")
                        except Exception as e:
                            print(f"[webcodecs-decoder] Failed to open {media_id}: {e}")

    async def play_at(self, show_id: str, target_time_ms: int | None, payload: dict[str, Any]) -> None:
        print(f"[webcodecs-decoder] Playing {show_id} at {target_time_ms}")
        # In a real implementation, we would start background decoding tasks here
        # and push frames into queues for the renderer to consume.
        # For now, we stub the start of decoding logic.
        for media_id in self.containers:
            if media_id not in self._decode_tasks:
                self._decode_tasks[media_id] = asyncio.create_task(self._decode_loop(media_id))

    async def _decode_loop(self, media_id: str):
        container = self.containers[media_id]
        stream = container.streams.video[0]
        print(f"[webcodecs-decoder] Started decode loop for {media_id}")
        try:
            for frame in container.decode(stream):
                # Simulate frame pacing or queueing
                # In a real app, this would be highly optimized (zero-copy if possible)
                await asyncio.sleep(0.016) # ~60fps
                if media_id not in self.containers:
                    break
        except Exception as e:
            print(f"[webcodecs-decoder] Decode error for {media_id}: {e}")

    async def close(self) -> None:
        print(f"[webcodecs-decoder] Closing.")
        for task in self._decode_tasks.values():
            task.cancel()
        for container in self.containers.values():
            container.close()
        self.containers.clear()
        self._decode_tasks.clear()
