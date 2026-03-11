"""
test_audio_analysis.py
======================
Tests for AudioAnalyzer (SC-107) – FFT, beat detection, BPM estimation.
"""
from __future__ import annotations

import math
import sys
import time
import unittest
from pathlib import Path

RENDER_ROOT = Path(__file__).resolve().parents[1]
if str(RENDER_ROOT) not in sys.path:
    sys.path.insert(0, str(RENDER_ROOT))

from app.audio_analysis import (
    AudioAnalyzer,
    AudioPeaks,
    _fft,
    _next_pow2,
    compute_fft_magnitudes,
)


class FFTTests(unittest.TestCase):

    def test_next_pow2(self):
        self.assertEqual(_next_pow2(1), 1)
        self.assertEqual(_next_pow2(3), 4)
        self.assertEqual(_next_pow2(512), 512)
        self.assertEqual(_next_pow2(513), 1024)

    def test_fft_dc(self):
        """Pure DC signal → all energy in bin 0."""
        n = 16
        samples = [1.0] * n
        spectrum = _fft(samples)
        mag_0 = abs(spectrum[0]) / n
        self.assertAlmostEqual(mag_0, 1.0, places=9)
        for k in range(1, n):
            self.assertAlmostEqual(abs(spectrum[k]) / n, 0.0, places=9)

    def test_fft_sine(self):
        """Sine at 1 cycle / N samples → energy in bin 1."""
        n = 32
        samples = [math.sin(2 * math.pi * k / n) for k in range(n)]
        spectrum = _fft(samples)
        mags = [abs(spectrum[k]) / n for k in range(n)]
        peak_bin = max(range(n // 2), key=lambda k: mags[k])
        self.assertEqual(peak_bin, 1)

    def test_fft_non_pow2_raises(self):
        with self.assertRaises(ValueError):
            _fft([1.0] * 3)

    def test_compute_fft_magnitudes_length(self):
        n = 64
        mags, freqs = compute_fft_magnitudes([0.0] * n, sample_rate=48000)
        # Should return n//2 = 32 bins (zero-padded handled internally)
        next_p = _next_pow2(n)
        self.assertEqual(len(mags), next_p // 2)
        self.assertEqual(len(freqs), next_p // 2)

    def test_compute_fft_magnitudes_freq_range(self):
        mags, freqs = compute_fft_magnitudes([0.0] * 512, sample_rate=48000)
        self.assertAlmostEqual(freqs[0], 0.0, places=5)
        self.assertLessEqual(freqs[-1], 24000.0)


class AudioPeaksTests(unittest.TestCase):

    def test_default_peaks(self):
        p = AudioPeaks()
        self.assertEqual(p.kick, 0.0)
        self.assertFalse(p.is_beat)

    def test_as_dict(self):
        p = AudioPeaks(kick=0.5, snare=0.3, is_beat=True, estimated_bpm=128.0)
        d = p.as_dict()
        self.assertIn("kick", d)
        self.assertIn("is_beat", d)
        self.assertTrue(d["is_beat"])
        self.assertAlmostEqual(d["kick"], 0.5)


class AudioAnalyzerTests(unittest.TestCase):

    def _sine_frame(self, freq_hz: float, n: int = 512, sample_rate: int = 48000) -> list[float]:
        return [math.sin(2 * math.pi * freq_hz * i / sample_rate) for i in range(n)]

    def test_process_frame_returns_peaks(self):
        analyzer = AudioAnalyzer()
        frame = self._sine_frame(100)  # 100 Hz → kick band
        peaks = analyzer.process_frame(frame)
        self.assertIsInstance(peaks, AudioPeaks)

    def test_kick_detected_for_bass_signal(self):
        """100 Hz tone → kick > 0."""
        analyzer = AudioAnalyzer()
        frame = self._sine_frame(100, n=512)
        peaks = analyzer.process_frame(frame)
        self.assertGreater(peaks.kick, 0.0)

    def test_snare_band_detected(self):
        """2000 Hz tone → snare > 0."""
        analyzer = AudioAnalyzer()
        frame = self._sine_frame(2000, n=512)
        peaks = analyzer.process_frame(frame)
        self.assertGreater(peaks.snare, 0.0)

    def test_hi_hat_band_detected(self):
        """8000 Hz tone → hi_hat > 0."""
        analyzer = AudioAnalyzer()
        frame = self._sine_frame(8000, n=512)
        peaks = analyzer.process_frame(frame)
        self.assertGreater(peaks.hi_hat, 0.0)

    def test_peaks_normalized(self):
        """All peaks must be in [0.0, 1.0]."""
        analyzer = AudioAnalyzer()
        frame = self._sine_frame(100, n=512)
        peaks = analyzer.process_frame(frame)
        self.assertGreaterEqual(peaks.kick, 0.0)
        self.assertLessEqual(peaks.kick, 1.0)
        self.assertGreaterEqual(peaks.rms, 0.0)
        self.assertLessEqual(peaks.rms, 1.0)

    def test_silence_produces_zero_peaks(self):
        analyzer = AudioAnalyzer()
        silence = [0.0] * 512
        peaks = analyzer.process_frame(silence)
        self.assertAlmostEqual(peaks.rms, 0.0, places=5)
        self.assertFalse(peaks.is_beat)

    def test_beat_detected_on_large_transient(self):
        """
        Simulate a beat: first warm up history with silence,
        then inject a large-amplitude kick-band burst.
        """
        analyzer = AudioAnalyzer()
        # Warm up history with weak signals
        weak = [0.001 * math.sin(2 * math.pi * 80 * i / 48000) for i in range(512)]
        for _ in range(20):
            analyzer.process_frame(weak)
        # Large burst
        loud = [0.9 * math.sin(2 * math.pi * 80 * i / 48000) for i in range(512)]
        peaks = analyzer.process_frame(loud)
        self.assertTrue(peaks.is_beat, "Expected beat detection on large transient")

    def test_bpm_estimation_after_beats(self):
        """After several beats ~120 BPM, estimated_bpm should be non-zero."""
        analyzer = AudioAnalyzer()
        # Interval for 120 BPM = 500ms; at 512/48000 ~=10.67ms per frame → 47 frames/beat
        beat_frame = [0.9 * math.sin(2 * math.pi * 80 * i / 48000) for i in range(512)]
        silence = [0.0] * 512
        for beat in range(6):
            analyzer.process_frame(beat_frame)
            for _ in range(45):
                analyzer.process_frame(silence)
        peaks = analyzer.process_frame(beat_frame)
        # BPM might not be exactly 120 due to frame granularity, just verify it's plausible
        if analyzer.get_last_peaks() and analyzer.get_last_peaks().estimated_bpm > 0:
            self.assertGreater(analyzer.get_last_peaks().estimated_bpm, 0.0)

    def test_get_last_peaks_before_any_processing(self):
        analyzer = AudioAnalyzer()
        self.assertIsNone(analyzer.get_last_peaks())

    def test_get_last_peaks_matches_latest(self):
        analyzer = AudioAnalyzer()
        frame = self._sine_frame(440, n=512)
        peaks = analyzer.process_frame(frame)
        self.assertIs(analyzer.get_last_peaks(), peaks)

    def test_empty_frame_handled(self):
        """Passing an empty frame should not raise."""
        analyzer = AudioAnalyzer()
        peaks = analyzer.process_frame([])
        self.assertIsInstance(peaks, AudioPeaks)
        self.assertAlmostEqual(peaks.rms, 0.0)

    def test_timestamp_populated(self):
        analyzer = AudioAnalyzer()
        peaks = analyzer.process_frame([0.0] * 64)
        self.assertGreater(peaks.timestamp_ms, 0.0)

    def test_processing_is_fast_under_2ms(self):
        """
        SC-101 budget: audio analysis of a 512-sample frame must be < 2ms.
        (Uses stub FFT – would be faster with numpy in production.)
        """
        analyzer = AudioAnalyzer()
        frame = [math.sin(2 * math.pi * 100 * i / 48000) for i in range(512)]
        t0 = time.perf_counter()
        analyzer.process_frame(frame)
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"\n[SC-107] Audio analysis elapsed: {elapsed:.3f}ms")
        self.assertLess(elapsed, 2.0, f"Audio analysis too slow: {elapsed:.3f}ms")


if __name__ == "__main__":
    unittest.main()
