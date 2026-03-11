"""
test_audio_engine.py
====================
Tests for AudioEngine (SC-106) – multi-channel non-blocking playback.
"""
from __future__ import annotations

import sys
import math
import threading
import time
import unittest
from pathlib import Path

RENDER_ROOT = Path(__file__).resolve().parents[1]
if str(RENDER_ROOT) not in sys.path:
    sys.path.insert(0, str(RENDER_ROOT))

from app.audio_engine import AudioBuffer, AudioEngine, MAX_CHANNELS, FRAMES_PER_BUFFER


class AudioBufferTests(unittest.TestCase):

    def test_push_and_drain(self):
        buf = AudioBuffer(capacity_frames=16)
        frame = [0.5] * 8
        buf.push(frame)
        drained = buf.drain(1)
        self.assertEqual(len(drained), 1)
        self.assertEqual(drained[0], frame)

    def test_drain_more_than_available(self):
        buf = AudioBuffer(capacity_frames=16)
        buf.push([0.1] * 4)
        drained = buf.drain(10)
        self.assertEqual(len(drained), 1)  # only 1 was pushed

    def test_ring_buffer_capacity(self):
        capacity = 4
        buf = AudioBuffer(capacity_frames=capacity)
        for i in range(capacity + 5):
            buf.push([float(i)] * 2)
        # maxlen means oldest evicted
        self.assertEqual(len(buf), capacity)

    def test_thread_safety(self):
        buf = AudioBuffer(capacity_frames=100)
        results = []
        def producer():
            for _ in range(50):
                buf.push([1.0, -1.0])
        def consumer():
            time.sleep(0.01)
            results.extend(buf.drain(50))
        t1 = threading.Thread(target=producer)
        t2 = threading.Thread(target=consumer)
        t1.start(); t2.start()
        t1.join(); t2.join()
        self.assertGreater(len(results), 0)


class AudioEngineTests(unittest.TestCase):

    def test_channel_limits(self):
        with self.assertRaises(ValueError):
            AudioEngine(num_channels=0)
        with self.assertRaises(ValueError):
            AudioEngine(num_channels=MAX_CHANNELS + 1)

    def test_start_and_stop(self):
        engine = AudioEngine(num_channels=2)
        engine.start()
        time.sleep(0.05)
        self.assertTrue(engine._thread is not None)
        engine.stop()

    def test_metrics_populated_after_start(self):
        engine = AudioEngine(num_channels=4)
        engine.load_stems({"kick": b"\x00" * 2048, "snare": b"\x00" * 2048})
        engine.start()
        time.sleep(0.12)
        metrics = engine.get_metrics()
        engine.stop()
        self.assertIn("position_ms", metrics)
        self.assertGreater(metrics["position_ms"], 0.0)
        self.assertIn("rms_per_channel", metrics)
        self.assertEqual(len(metrics["rms_per_channel"]), 4)

    def test_get_channel_samples_without_stems(self):
        engine = AudioEngine(num_channels=2)
        engine.start()
        time.sleep(0.02)
        frames = engine.get_channel_samples(0, 4)
        engine.stop()
        # Without stems, no frames are pushed → empty
        self.assertEqual(frames, [])

    def test_get_channel_samples_with_stems(self):
        engine = AudioEngine(num_channels=2)
        # Load a simple stub stem
        engine.load_stems({"ch0": b"\x00" * (FRAMES_PER_BUFFER * 4 * 4)})
        engine.start()
        time.sleep(0.15)  # Allow a few callback cycles
        frames = engine.get_channel_samples(0, 4)
        engine.stop()
        self.assertGreater(len(frames), 0)

    def test_audio_thread_does_not_block_main(self):
        """
        The audio thread is a daemon thread; it must not block the calling thread.
        """
        engine = AudioEngine(num_channels=16)
        engine.load_stems({f"ch{i}": b"\x00" * 512 for i in range(16)})
        t0 = time.perf_counter()
        engine.start()
        startup_ms = (time.perf_counter() - t0) * 1000
        engine.stop()
        # start() should return in << 50ms
        self.assertLess(startup_ms, 50.0, f"AudioEngine.start() blocked for {startup_ms:.1f}ms")

    def test_underrun_counter_exists(self):
        engine = AudioEngine(num_channels=1)
        metrics = engine.get_metrics()
        self.assertIn("underruns", metrics)
        self.assertIsInstance(metrics["underruns"], int)


if __name__ == "__main__":
    unittest.main()
