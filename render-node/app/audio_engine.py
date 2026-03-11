"""
audio_engine.py
===============
SC-106: Multi-Channel Audio Playback Engine

Manages up to 16 channels of audio output, locked to the internal high-precision
perf_counter scheduler. Runs in a dedicated daemon thread so it NEVER blocks
the WebGPU render loop or the async event loop.

Key design decisions:
- Thread-safe: AudioEngine state is accessed via threading.Lock.
- Non-blocking: The audio callback is decoupled from the renderer tick.
- Extensible: Real ASIO/CoreAudio device binding can replace the stub in `_audio_callback`.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from collections import deque
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_CHANNELS = 16
SAMPLE_RATE = 48000            # 48 kHz – broadcast standard
FRAMES_PER_BUFFER = 512        # Latency: ~10.67ms at 48kHz
CHANNEL_DTYPE = float          # Interleaved float32 samples per channel
BUFFER_SECONDS = 2.0           # Ring-buffer capacity for stem audio


class AudioBuffer:
    """
    Thread-safe ring buffer for PCM audio data per channel.
    Backed by a deque of frames (numpy-free for portability).
    """
    def __init__(self, capacity_frames: int):
        self._buf: deque[list[float]] = deque(maxlen=capacity_frames)
        self._lock = threading.Lock()

    def push(self, frame: list[float]) -> None:
        with self._lock:
            self._buf.append(frame)

    def drain(self, n: int) -> list[list[float]]:
        frames: list[list[float]] = []
        with self._lock:
            for _ in range(min(n, len(self._buf))):
                frames.append(self._buf.popleft())
        return frames

    def __len__(self) -> int:
        with self._lock:
            return len(self._buf)


class AudioEngine:
    """
    SC-106: Multi-Channel Audio Playback Engine.

    Usage::
        engine = AudioEngine(num_channels=16)
        engine.start()
        engine.load_stems({"kick": kick_bytes, "snare": snare_bytes, ...})
        # Later, in tick():
        metrics = engine.get_metrics()
        engine.stop()
    """

    def __init__(self, num_channels: int = MAX_CHANNELS, sample_rate: int = SAMPLE_RATE):
        if not 1 <= num_channels <= MAX_CHANNELS:
            raise ValueError(f"num_channels must be 1–{MAX_CHANNELS}, got {num_channels}")

        self.num_channels = num_channels
        self.sample_rate = sample_rate
        self.frames_per_buffer = FRAMES_PER_BUFFER

        # Per-channel ring buffers
        self._buffers: list[AudioBuffer] = [
            AudioBuffer(capacity_frames=int(BUFFER_SECONDS * sample_rate / FRAMES_PER_BUFFER))
            for _ in range(num_channels)
        ]

        # Stem library: name → list of PCM frame chunks (stub; real impl uses decode pipeline)
        self._stems: dict[str, list[list[float]]] = {}
        self._stem_cursors: dict[str, int] = {}

        # Playback state
        self._playing = False
        self._start_perf = 0.0
        self._lock = threading.Lock()

        # Metrics available to the renderer
        self._metrics: dict[str, Any] = {
            "underruns": 0,
            "position_ms": 0.0,
            "channels_active": 0,
            "rms_per_channel": [0.0] * num_channels,
        }

        # Background thread
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_stems(self, stems: dict[str, bytes]) -> None:
        """
        Load raw PCM (stub: single-channel float32) stems into the engine.
        Each stem is mapped to a channel index in insertion order.
        """
        with self._lock:
            self._stems = {}
            self._stem_cursors = {}
            for name, raw_bytes in stems.items():
                # Decode stub: interpret raw bytes as little-endian float32 samples
                # In a real engine this goes through FFmpeg/libsndfile decode.
                n_floats = len(raw_bytes) // 4
                samples = [
                    math.sin(2 * math.pi * 440 * i / self.sample_rate)  # test tone
                    for i in range(n_floats or FRAMES_PER_BUFFER * 16)
                ]
                # Chunk into FRAMES_PER_BUFFER frames
                chunks = [
                    samples[i:i + FRAMES_PER_BUFFER]
                    for i in range(0, len(samples), FRAMES_PER_BUFFER)
                ]
                self._stems[name] = chunks
                self._stem_cursors[name] = 0
            logger.info(f"[audio-engine] Loaded {len(self._stems)} stems into {self.num_channels}-channel engine.")

    def start(self) -> None:
        """Start the audio playback thread (non-blocking to the event loop)."""
        if self._thread and self._thread.is_alive():
            logger.warning("[audio-engine] Already running.")
            return
        self._stop_event.clear()
        self._playing = True
        self._start_perf = time.perf_counter()
        self._thread = threading.Thread(
            target=self._audio_loop,
            name="AudioEngine-Thread",
            daemon=True
        )
        self._thread.start()
        logger.info(f"[audio-engine] Started. {self.num_channels} channels @ {self.sample_rate} Hz.")

    def stop(self) -> None:
        """Stop the audio thread gracefully."""
        self._stop_event.set()
        self._playing = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("[audio-engine] Stopped.")

    def get_metrics(self) -> dict[str, Any]:
        """Thread-safe snapshot of current playback metrics."""
        with self._lock:
            return dict(self._metrics)

    def get_channel_samples(self, channel: int, n_frames: int) -> list[list[float]]:
        """Return up to `n_frames` audio frames from channel `channel`."""
        if channel >= self.num_channels:
            return []
        return self._buffers[channel].drain(n_frames)

    # ------------------------------------------------------------------
    # Internal audio loop (runs on background thread)
    # ------------------------------------------------------------------

    def _audio_loop(self) -> None:
        """
        Main audio thread loop.
        Fires every FRAMES_PER_BUFFER / sample_rate seconds to
        simulate a real audio callback (CoreAudio/ASIO) at < 1ms jitter.
        """
        tick_interval = FRAMES_PER_BUFFER / self.sample_rate
        next_tick = time.perf_counter()

        stem_names = []
        stem_rms: list[float] = [0.0] * self.num_channels

        while not self._stop_event.is_set():
            now = time.perf_counter()

            # Busy-wait for sub-millisecond precision (real app uses ASIO callback)
            if now < next_tick:
                time.sleep(max(0, next_tick - now - 0.0005))
                continue

            # --- Callback body ---
            with self._lock:
                stem_names = list(self._stems.keys())
                pos_ms = (time.perf_counter() - self._start_perf) * 1000.0
                self._metrics["position_ms"] = pos_ms

            underrun = False
            active_ch = 0

            for ch_idx, stem_name in enumerate(stem_names[:self.num_channels]):
                with self._lock:
                    chunks = self._stems.get(stem_name, [])
                    cursor = self._stem_cursors.get(stem_name, 0)

                if not chunks:
                    continue

                active_ch += 1
                frame = chunks[cursor % len(chunks)]

                # Push to per-channel ring-buffer
                self._buffers[ch_idx].push(frame)

                # Calculate RMS
                rms = math.sqrt(sum(s * s for s in frame) / max(len(frame), 1))
                stem_rms[ch_idx] = round(rms, 5)

                with self._lock:
                    self._stem_cursors[stem_name] = (cursor + 1) % len(chunks)

                if len(self._buffers[ch_idx]) == 0 and len(chunks) > 0:
                    underrun = True

            with self._lock:
                if underrun:
                    self._metrics["underruns"] += 1
                self._metrics["channels_active"] = active_ch
                self._metrics["rms_per_channel"] = stem_rms[:self.num_channels]

            next_tick += tick_interval
