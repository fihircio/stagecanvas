from __future__ import annotations

import logging
import math
import time
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.audio_analysis import AudioPeaks

logger = logging.getLogger(__name__)


class GenerativeAILayer:
    """
    Generative AI Layer (SD-Lite).
    Accepts text prompts and generates frames (currently stubbed).
    SC-107: Also accepts AudioPeaks to make visuals pulse to the beat.
    """
    def __init__(self, layer_id: str):
        self.layer_id = layer_id
        self.prompt = ""
        self.last_prompt = ""
        self.is_generating = False
        self.frame_data: Optional[bytes] = None
        self.width = 512
        self.height = 512

        # SC-107: Audio reactive state
        self._audio_intensity: float = 0.0   # 0.0–1.0 modulation factor
        self._beat_flash_t: float = 0.0       # perf_counter time of last beat
        self.BEAT_FLASH_DECAY = 0.25          # seconds to decay beat flash

    def update_prompt(self, prompt: str) -> None:
        if prompt != self.prompt:
            self.prompt = prompt
            logger.info(f"[layer-gen-ai] New prompt for {self.layer_id}: {prompt}")
            self._generate_frame()

    def update_audio_peaks(self, peaks: "AudioPeaks") -> None:
        """
        SC-107: Feed live AudioPeaks from the analyzer.
        Raise intensity on kick hits; maintain a decaying flash for snare.
        """
        now = time.perf_counter()

        # Blend kick energy and general RMS into intensity
        self._audio_intensity = min(peaks.kick * 0.7 + peaks.rms * 0.3, 1.0)

        if peaks.is_beat:
            self._beat_flash_t = now
            logger.debug(f"[layer-gen-ai] Beat! strength={peaks.beat_strength:.3f} bpm={peaks.estimated_bpm}")

        # Re-generate frame if significant beat impact (threshold to avoid spam)
        if peaks.beat_strength > 0.6 and self.prompt:
            self._generate_frame()

    def get_audio_intensity(self) -> float:
        """Return current audio modulation intensity with beat-flash decay applied."""
        now = time.perf_counter()
        age = now - self._beat_flash_t
        flash_boost = max(0.0, 1.0 - age / self.BEAT_FLASH_DECAY) * 0.5
        return min(self._audio_intensity + flash_boost, 1.0)

    def _generate_frame(self) -> None:
        """Stub for triggering a generative AI pipeline."""
        self.is_generating = True
        intensity = self.get_audio_intensity()
        # Modulate stub colour by intensity – higher intensity → brighter frame
        v = int(0x44 + intensity * (0xFF - 0x44)) & 0xFF
        self.frame_data = bytes([v, v, v, 0xFF]) * (self.width * self.height)
        self.last_prompt = self.prompt
        self.is_generating = False
        logger.info(f"[layer-gen-ai] Frame generated for {self.layer_id} (intensity={intensity:.2f})")

    def get_current_frame(self) -> Optional[bytes]:
        return self.frame_data
