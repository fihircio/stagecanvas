"""
audio_analysis.py
=================
SC-107: AI Generative Stems – Audio Reactive Analysis

Processes live audio frames from AudioEngine to extract:
  1. Frequency bands via FFT (stub implementation without numpy)
  2. Kick drum / snare peaks via energy threshold detection
  3. Beat strength per frame – published as AudioPeaks dataclass

All methods are designed to be called from the main render tick
without blocking. Computation is O(N log N) FFT per-frame.
"""
from __future__ import annotations

import cmath
import math
import time
from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Data structures exposed to the renderer
# ---------------------------------------------------------------------------

@dataclass
class AudioPeaks:
    """
    Real-time audio peak data published to the generative AI layer.
    All values are in the range [0.0, 1.0] except BPM.
    """
    kick: float = 0.0           # Kick drum energy (sub-bass band, 20–150 Hz)
    snare: float = 0.0          # Snare energy (upper-mid band, 150–4000 Hz)
    hi_hat: float = 0.0         # Hi-hat / cymbal energy (high band, > 4000 Hz)
    rms: float = 0.0            # Overall loudness
    is_beat: bool = False       # True for frames containing a beat drop
    beat_strength: float = 0.0  # 0.0–1.0 normalized transient strength
    estimated_bpm: float = 0.0  # Live estimated BPM (simple onset-to-onset)
    timestamp_ms: float = 0.0  # perf_counter timestamp in ms

    def as_dict(self) -> dict[str, Any]:
        return {
            "kick": self.kick,
            "snare": self.snare,
            "hi_hat": self.hi_hat,
            "rms": self.rms,
            "is_beat": self.is_beat,
            "beat_strength": self.beat_strength,
            "estimated_bpm": self.estimated_bpm,
            "timestamp_ms": self.timestamp_ms,
        }


# ---------------------------------------------------------------------------
# Pure-Python FFT (Cooley-Tukey, radix-2 DIT)
# ---------------------------------------------------------------------------

def _fft(x: list[float]) -> list[complex]:
    """
    Recursive Cooley-Tukey FFT.
    Input length must be a power of 2 (caller is responsible for zero-padding).
    """
    n = len(x)
    if n <= 1:
        return [complex(v) for v in x]
    if n & (n - 1):
        raise ValueError(f"FFT length must be power of 2, got {n}")

    evens = _fft(x[0::2])
    odds = _fft(x[1::2])
    twiddles = [cmath.exp(-2j * cmath.pi * k / n) * odds[k] for k in range(n // 2)]
    return [evens[k] + twiddles[k] for k in range(n // 2)] + \
           [evens[k] - twiddles[k] for k in range(n // 2)]


def _next_pow2(n: int) -> int:
    p = 1
    while p < n:
        p <<= 1
    return p


def compute_fft_magnitudes(samples: list[float], sample_rate: int = 48000) -> tuple[list[float], list[float]]:
    """
    Compute FFT magnitudes and corresponding frequency bins.
    Returns (magnitudes, freqs) — both length N//2.
    """
    n_orig = len(samples)
    n = _next_pow2(n_orig)
    padded = samples + [0.0] * (n - n_orig)
    spectrum = _fft(padded)
    half = n // 2
    magnitudes = [abs(spectrum[k]) / n for k in range(half)]
    freqs = [k * sample_rate / n for k in range(half)]
    return magnitudes, freqs


# ---------------------------------------------------------------------------
# Frequency band integration helper
# ---------------------------------------------------------------------------

def _band_energy(magnitudes: list[float], freqs: list[float], f_lo: float, f_hi: float) -> float:
    """Integrate magnitudes within [f_lo, f_hi] Hz band."""
    energy = sum(m for m, f in zip(magnitudes, freqs) if f_lo <= f < f_hi)
    return energy


# ---------------------------------------------------------------------------
# Main analyser class
# ---------------------------------------------------------------------------

class AudioAnalyzer:
    """
    SC-107: Real-time audio analysis for AI-reactive visuals.

    Typical usage (from render tick)::

        analyzer = AudioAnalyzer(sample_rate=48000)
        # Feed each audio frame from AudioEngine:
        peaks: AudioPeaks = analyzer.process_frame(samples)
        # Pass peaks to the generative AI layer
        gen_ai_layer.update_audio_peaks(peaks)
    """

    # Frequency band boundaries (Hz)
    KICK_LO, KICK_HI = 20, 150
    SNARE_LO, SNARE_HI = 150, 4000
    HIHAT_LO, HIHAT_HI = 4000, 20000

    # Beat detection thresholds
    BEAT_THRESHOLD_RATIO = 2.0   # Energy must be >2x recent average to flag a beat
    BEAT_HOLD_MS = 80.0          # Minimum ms between consecutive beat flags (debounce)

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate
        self._history_window = 43  # ~1 second at 48kHz/512 frames ~= 93.75 frames/sec → ~43 frames for 460ms
        self._energy_history: list[float] = []
        self._beat_timestamps: list[float] = []  # perf_counter timestamps
        self._last_beat_t: float = 0.0
        self._last_peaks: Optional[AudioPeaks] = None

    def process_frame(self, samples: list[float]) -> AudioPeaks:
        """
        Analyse a single PCM frame and return an AudioPeaks snapshot.
        Designed to be called once per render tick from the main thread.
        Thread-safe: reads from a list that's replaced atomically.
        """
        now_ms = time.perf_counter() * 1000.0

        # --- RMS ---
        rms = math.sqrt(sum(s * s for s in samples) / max(len(samples), 1)) if samples else 0.0

        # --- FFT ---
        mags: list[float] = []
        freqs: list[float] = []
        if len(samples) >= 4:
            mags, freqs = compute_fft_magnitudes(samples, self.sample_rate)

        # --- Per-band energy ---
        kick = _band_energy(mags, freqs, self.KICK_LO, self.KICK_HI) if mags else 0.0
        snare = _band_energy(mags, freqs, self.SNARE_LO, self.SNARE_HI) if mags else 0.0
        hi_hat = _band_energy(mags, freqs, self.HIHAT_LO, self.HIHAT_HI) if mags else 0.0

        # Normalise to [0, 1] by clamping at a practical max
        kick_norm = min(kick / 0.5, 1.0)
        snare_norm = min(snare / 1.0, 1.0)
        hihat_norm = min(hi_hat / 0.5, 1.0)

        # --- Beat detection (flux on kick band) ---
        self._energy_history.append(kick)
        if len(self._energy_history) > self._history_window:
            self._energy_history.pop(0)

        avg_energy = sum(self._energy_history) / max(len(self._energy_history), 1)
        is_beat = (
            kick > avg_energy * self.BEAT_THRESHOLD_RATIO
            and (now_ms - self._last_beat_t) > self.BEAT_HOLD_MS
            and kick > 0.001
        )
        if is_beat:
            self._last_beat_t = now_ms
            self._beat_timestamps.append(now_ms)
            # Keep last 8 beats for BPM estimation
            if len(self._beat_timestamps) > 8:
                self._beat_timestamps.pop(0)

        # --- Beat strength: normalised instantaneous flux ---
        beat_str = min(kick / max(avg_energy, 1e-9) - 1.0, 1.0) if avg_energy > 0 else 0.0
        beat_str = max(beat_str, 0.0)

        # --- BPM estimation from inter-beat intervals ---
        bpm = 0.0
        if len(self._beat_timestamps) >= 2:
            intervals = [
                self._beat_timestamps[i + 1] - self._beat_timestamps[i]
                for i in range(len(self._beat_timestamps) - 1)
            ]
            avg_interval_ms = sum(intervals) / len(intervals)
            if avg_interval_ms > 0:
                bpm = round(60_000.0 / avg_interval_ms, 1)

        peaks = AudioPeaks(
            kick=kick_norm,
            snare=snare_norm,
            hi_hat=hihat_norm,
            rms=min(rms * 4.0, 1.0),
            is_beat=is_beat,
            beat_strength=beat_str,
            estimated_bpm=bpm,
            timestamp_ms=now_ms,
        )
        self._last_peaks = peaks
        return peaks

    def get_last_peaks(self) -> Optional[AudioPeaks]:
        """Return the most recently computed peaks without re-processing."""
        return self._last_peaks
