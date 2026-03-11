import asyncio
import time
import logging
from typing import Callable, Optional, List, Any
from ..models import ControlCommand

logger = logging.getLogger("orchestration.scheduler")

class TimelineScheduler:
    def __init__(self, dispatch_callback: Callable[[str, dict], Any]):
        self.playhead_ms = 0
        self.is_playing = False
        self.show_duration_ms = 0
        self.tracks = []
        self.dispatch_callback = dispatch_callback
        self._loop_task: Optional[asyncio.Task] = None
        self._last_tick_time: float = 0.0
        self._fps = 60
        self._frame_time = 1.0 / self._fps

    def load_show_data(self, show_snapshot: Any):
        self.tracks = show_snapshot.tracks
        self.show_duration_ms = show_snapshot.duration_ms
        self.playhead_ms = show_snapshot.playhead_ms
        logger.info(f"[scheduler] Loaded show duration={self.show_duration_ms}ms tracks={len(self.tracks)}")

    async def start(self):
        if self.is_playing:
            return
        self.is_playing = True
        self._last_tick_time = time.perf_counter()
        if not self._loop_task or self._loop_task.done():
            self._loop_task = asyncio.create_task(self._run_loop())
        logger.info("[scheduler] Started playback")

    async def pause(self):
        self.is_playing = False
        logger.info("[scheduler] Paused playback")

    async def stop(self):
        self.is_playing = False
        self.playhead_ms = 0
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except (asyncio.CancelledError, Exception):
                pass
            self._loop_task = None
        logger.info("[scheduler] Stopped playback and reset playhead")

    async def seek(self, position_ms: int):
        self.playhead_ms = max(0, min(position_ms, self.show_duration_ms))
        logger.info(f"[scheduler] Seek to {self.playhead_ms}ms")
        await self.dispatch_callback("SEEK", {"position_ms": self.playhead_ms})

    async def _run_loop(self):
        try:
            while True:
                if not self.is_playing:
                    await asyncio.sleep(0.1)
                    continue

                now = time.perf_counter()
                dt = now - self._last_tick_time
                self._last_tick_time = now

                prev_playhead = self.playhead_ms
                self.playhead_ms += int(dt * 1000)

                if self.playhead_ms >= self.show_duration_ms:
                    self.playhead_ms = self.show_duration_ms
                    self.is_playing = False
                    logger.info("[scheduler] Reached end of show")

                # Evaluate active clips
                for track in self.tracks:
                    for clip in track.clips:
                        # Check if clip should start in this tick
                        if prev_playhead < clip.start_ms <= self.playhead_ms:
                            logger.info(f"[scheduler] Firing clip {clip.clip_id} on track {track.track_id}")
                            # For simplicity, we send the first layer's info. 
                            # Production would handle multi-layer clips.
                            payload = {
                                "clip_id": clip.clip_id,
                                "track_id": track.track_id,
                                "start_ms": clip.start_ms,
                                "duration_ms": clip.duration_ms,
                                "layers": [l.model_dump() for l in clip.layers]
                            }
                            await self.dispatch_callback("PLAY_CLIP", payload)

                # Maintain 60fps
                elapsed = time.perf_counter() - now
                sleep_time = max(0.0, self._frame_time - elapsed)
                await asyncio.sleep(sleep_time)
        except asyncio.CancelledError:
            logger.info("[scheduler] Loop task cancelled")
        except Exception as e:
            logger.error(f"[scheduler] Loop error: {e}")
            self.is_playing = False
