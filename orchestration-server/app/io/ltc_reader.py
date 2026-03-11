"""
SMPTE LTC (Linear Timecode) Reader
SC-100

Parses SMPTE biphase-mark encoded timecode from an audio stream and converts
it to a millisecond playhead position.

Supported frame rates: 24, 25, 29.97 (drop-frame), 30
Sync modes: CHASE, JAM_SYNC, FREE_WHEEL
"""
from __future__ import annotations

import asyncio
import time
import logging
from enum import Enum
from typing import Callable, Any

logger = logging.getLogger("ltc_reader")


# ---------------------------------------------------------------------------
# SMPTE LTC word structure (80 bits → 10 bytes per frame)
# Bit layout (simplified, non-drop-frame):
#   bits 0-3   : frame units         bits 4-7   : user bits 1
#   bits 8-9   : frame tens          bits 10-11 : flags (color-frame, drop)
#   bits 12-15 : user bits 2         bits 16-19 : seconds units
#   bits 20-23 : user bits 3         bits 24-26 : seconds tens
#   bit  27    : biphase-mark-phase  bits 28-31 : user bits 4
#   bits 32-35 : minutes units       bits 36-39 : user bits 5
#   bits 40-42 : minutes tens        bit  43    : BGF0
#   bits 44-47 : user bits 6         bits 48-51 : hours units
#   bits 52-55 : user bits 7         bits 56-57 : hours tens
#   bits 58-59 : flags               bits 60-63 : user bits 8
#   bits 64-79 : sync word (0x3FFD in bit-reverse = 0011 1111 1111 1101)
# ---------------------------------------------------------------------------

SYNC_WORD = 0x3FFD  # 16-bit LTC sync word

SUPPORTED_FPS = {24, 25, 30}
# 29.97 is handled as drop-frame 30
DROP_FRAME_FPS = 29.97


def _parse_ltc_word(bits: int) -> dict[str, int]:
    """Extract H:M:S:F from a 64-bit LTC word (bits 0-63, sync excluded)."""
    frame_units  = (bits >> 0)  & 0xF
    frame_tens   = (bits >> 8)  & 0x3
    sec_units    = (bits >> 16) & 0xF
    sec_tens     = (bits >> 24) & 0x7
    min_units    = (bits >> 32) & 0xF
    min_tens     = (bits >> 40) & 0x7
    hour_units   = (bits >> 48) & 0xF
    hour_tens    = (bits >> 56) & 0x3
    drop_flag    = (bits >> 10) & 0x1

    return {
        "hours":   hour_tens * 10  + hour_units,
        "minutes": min_tens  * 10  + min_units,
        "seconds": sec_tens  * 10  + sec_units,
        "frames":  frame_tens * 10 + frame_units,
        "drop":    bool(drop_flag),
    }


def _timecode_to_ms(h: int, m: int, s: int, f: int, fps: float, drop: bool) -> int:
    """Convert SMPTE timecode to milliseconds.

    For drop-frame (29.97): frames are numbered 0-29 but frames 0 and 1
    of each minute (except every 10th minute) are dropped.
    """
    if drop and fps in (29.97, 30):
        # SMPTE drop-frame formula
        drop_fps = 30
        total_frames = (
            drop_fps * 3600 * h
            + drop_fps * 60 * m
            + drop_fps * s
            + f
            - 2 * (m - m // 10)  # subtract dropped frames
        )
        return int(total_frames * 1000 / 29.97)
    else:
        real_fps = fps if fps != 29.97 else 30
        total_frames = (
            int(real_fps) * 3600 * h
            + int(real_fps) * 60 * m
            + int(real_fps) * s
            + f
        )
        return int(total_frames * 1000 / real_fps)


# ---------------------------------------------------------------------------

class LTCSyncMode(str, Enum):
    CHASE    = "chase"       # playhead continuously follows LTC
    JAM_SYNC = "jam_sync"   # lock to LTC once, then free-wheel
    FREE_WHEEL = "free_wheel"  # ignore LTC; advance via local clock only


class LTCReader:
    """
    Reads SMPTE LTC timecode and drives the timeline playhead.

    In a real deployment this would consume PCM audio from an audio interface.
    This implementation provides:
      - A pure-Python LTC bit-parser (attach real audio via feed_bits()).
      - A simulation mode that generates a running timecode.
      - Configurable sync mode and frame rate.

    Usage::

        reader = LTCReader(fps=25, sync_mode=LTCSyncMode.CHASE, callback=my_cb)
        await reader.start()
        # … later …
        await reader.stop()
    """

    def __init__(
        self,
        fps: float = 25.0,
        sync_mode: LTCSyncMode = LTCSyncMode.CHASE,
        callback: Callable[[int, str], Any] | None = None,
        simulate: bool = True,
    ) -> None:
        self.fps = fps
        self.drop_frame = abs(fps - 29.97) < 0.01
        self.sync_mode = sync_mode
        self.callback = callback
        self.simulate = simulate

        self._locked = False
        self._position_ms: int = 0
        self._jam_base_ms: int = 0          # wall-clock time when jam occurred
        self._jam_position_ms: int = 0     # LTC position at jam point
        self._last_frame_str: str = "00:00:00:00"
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def locked(self) -> bool:
        return self._locked

    @property
    def timecode_ms(self) -> int:
        if self.sync_mode == LTCSyncMode.FREE_WHEEL and self._locked:
            elapsed = int(time.time() * 1000) - self._jam_base_ms
            return self._jam_position_ms + elapsed
        return self._position_ms

    @property
    def last_frame_str(self) -> str:
        return self._last_frame_str

    def set_mode(self, mode: LTCSyncMode, fps: float | None = None) -> None:
        """Dynamically switch sync mode (and optionally fps) at runtime."""
        self.sync_mode = mode
        if fps is not None:
            self.fps = fps
            self.drop_frame = abs(fps - 29.97) < 0.01
        self._locked = False
        logger.info(f"[ltc] Mode changed to {mode}, fps={self.fps}")

    def feed_bits(self, word_80: bytes) -> None:
        """Feed a real 80-bit LTC word (10 bytes) decoded from audio."""
        if len(word_80) < 10:
            return
        # Check sync word (last 2 bytes)
        sync = (word_80[9] << 8) | word_80[8]
        if sync != SYNC_WORD:
            return
        # Pack lower 8 bytes into a 64-bit integer
        bits = int.from_bytes(word_80[:8], "little")
        tc = _parse_ltc_word(bits)
        self._apply_timecode(tc)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _apply_timecode(self, tc: dict[str, int]) -> None:
        position_ms = _timecode_to_ms(
            tc["hours"], tc["minutes"], tc["seconds"], tc["frames"],
            self.fps, tc["drop"],
        )
        self._last_frame_str = (
            f"{tc['hours']:02d}:{tc['minutes']:02d}:"
            f"{tc['seconds']:02d}:{tc['frames']:02d}"
        )

        if self.sync_mode == LTCSyncMode.CHASE:
            self._position_ms = position_ms
            self._locked = True
            self._emit(position_ms)

        elif self.sync_mode == LTCSyncMode.JAM_SYNC:
            if not self._locked:
                # Perform jam: record LTC position and local wall-clock
                self._jam_position_ms = position_ms
                self._jam_base_ms = int(time.time() * 1000)
                self._locked = True
                self._emit(position_ms)
                logger.info(f"[ltc] JAM_SYNC locked to {self._last_frame_str}")
            # After jam: advance via local clock (handled in timecode_ms)

        elif self.sync_mode == LTCSyncMode.FREE_WHEEL:
            if not self._locked:
                self._jam_position_ms = position_ms
                self._jam_base_ms = int(time.time() * 1000)
                self._locked = True
                self._emit(position_ms)
                logger.info(f"[ltc] FREE_WHEEL locked to {self._last_frame_str}")
            # After initial lock: timecode_ms uses local clock

    def _emit(self, position_ms: int) -> None:
        if self.callback:
            if asyncio.iscoroutinefunction(self.callback):
                asyncio.create_task(self.callback(position_ms, self.sync_mode.value))
            else:
                self.callback(position_ms, self.sync_mode.value)

    # ------------------------------------------------------------------
    # Simulation loop
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self.simulate:
            self._task = asyncio.create_task(self._simulate_loop())
            logger.info(f"[ltc] Simulation started at {self.fps}fps mode={self.sync_mode}")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[ltc] Stopped")

    async def _simulate_loop(self) -> None:
        """Generate synthetic LTC frames for testing without real hardware."""
        frame_interval = 1.0 / (29.97 if self.drop_frame else self.fps)
        h, m, s, f = 0, 0, 0, 0
        max_frames = 30 if not self.drop_frame else 30

        while not self._stop_event.is_set():
            tc = {"hours": h, "minutes": m, "seconds": s, "frames": f,
                  "drop": self.drop_frame}
            self._apply_timecode(tc)

            # Advance frame counter
            f += 1
            if f >= max_frames:
                f = 0
                s += 1
                if s >= 60:
                    s = 0
                    m += 1
                    if m >= 60:
                        m = 0
                        h = (h + 1) % 24

            try:
                await asyncio.sleep(frame_interval)
            except asyncio.CancelledError:
                break
