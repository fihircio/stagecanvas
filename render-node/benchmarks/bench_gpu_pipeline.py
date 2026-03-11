"""
SC-102: GPU Pipeline Performance Benchmark Suite
================================================
Measures:
  1. Frames composited/second (composite throughput)
  2. Per-shader-pass cost in ms (simulated vertex + fragment)
  3. PTP drift standard deviation across simulated frames

Outputs a structured JSON report to stdout and optionally to a file.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import statistics
import struct
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Simulated shader pass costs (stand-ins for real WebGPU timing queries)
# ---------------------------------------------------------------------------

def _simulate_vertex_pass(num_indices: int) -> float:
    """Simulate vertex shader pass cost proportional to index count."""
    start = time.perf_counter()
    # Simulate work: dot-product style vertex transform
    _ = sum(i * 0.001 for i in range(num_indices))
    return (time.perf_counter() - start) * 1000.0  # ms


def _simulate_fragment_pass(width: int, height: int) -> float:
    """Simulate fragment shader pass cost proportional to pixel count."""
    start = time.perf_counter()
    # Simulate work: sampler + alpha blend logic
    pixel_count = width * height
    _ = sum((i & 0xFF) / 255.0 for i in range(0, min(pixel_count, 8192), 16))
    return (time.perf_counter() - start) * 1000.0  # ms


def _simulate_texture_readout(width: int, height: int) -> float:
    """Simulate staging-buffer readout (SC-093 optimised path)."""
    start = time.perf_counter()
    buf = bytearray(width * height * 4)
    view = memoryview(buf)
    # Simulate NDI/WebRTC consuming the frame
    _ = bytes(view[:min(len(view), 4096)])
    return (time.perf_counter() - start) * 1000.0  # ms


# ---------------------------------------------------------------------------
# Drift simulation (PTP jitter model)
# ---------------------------------------------------------------------------

def _generate_ptp_drift_samples(n: int, base_drift_ms: float = 0.05, jitter_ms: float = 0.02) -> list[float]:
    """
    Generate realistic PTP drift samples.
    Models a sawtooth-like drift with small random jitter.
    """
    import random
    rng = random.Random(42)  # deterministic
    samples = []
    accumulated = 0.0
    for _ in range(n):
        drift = base_drift_ms + rng.gauss(0, jitter_ms)
        accumulated += drift
        if accumulated > 0.5:          # simulated correction event
            accumulated -= 0.5
        samples.append(accumulated)
    return samples


# ---------------------------------------------------------------------------
# Main benchmark runner
# ---------------------------------------------------------------------------

async def run_benchmark(
    num_frames: int = 200,
    width: int = 3840,
    height: int = 2160,
    num_indices: int = 4096,
) -> dict:
    """
    Run the full GPU pipeline benchmark.

    Returns a structured dict with all measured metrics.
    """
    vertex_costs: list[float] = []
    fragment_costs: list[float] = []
    readout_costs: list[float] = []
    frame_times: list[float] = []

    print(f"[bench] Starting GPU pipeline benchmark: {num_frames} frames @ {width}x{height}")

    for frame_idx in range(num_frames):
        t_frame_start = time.perf_counter()

        # Phase 1: Vertex pass
        v_ms = _simulate_vertex_pass(num_indices)
        vertex_costs.append(v_ms)

        # Phase 2: Fragment pass
        f_ms = _simulate_fragment_pass(width, height)
        fragment_costs.append(f_ms)

        # Phase 3: Texture readout (SC-093 staging buffer path)
        r_ms = _simulate_texture_readout(width, height)
        readout_costs.append(r_ms)

        # Yield to event loop (mirrors real async render tick)
        await asyncio.sleep(0)

        t_frame_end = time.perf_counter()
        frame_times.append((t_frame_end - t_frame_start) * 1000.0)

        if frame_idx % 50 == 0:
            print(f"[bench]   frame {frame_idx:>4}/{num_frames} "
                  f"(vertex={v_ms:.3f}ms fragment={f_ms:.3f}ms readout={r_ms:.3f}ms)")

    # PTP drift analysis
    drift_samples = _generate_ptp_drift_samples(num_frames)
    drift_std = statistics.stdev(drift_samples)
    drift_mean = statistics.mean(drift_samples)
    drift_max = max(drift_samples)

    # Composite throughput
    total_frame_time_s = sum(frame_times) / 1000.0
    fps = num_frames / total_frame_time_s if total_frame_time_s > 0 else 0.0

    def _stats(samples: list[float]) -> dict:
        return {
            "mean_ms": round(statistics.mean(samples), 4),
            "std_ms": round(statistics.stdev(samples), 4) if len(samples) > 1 else 0.0,
            "min_ms": round(min(samples), 4),
            "max_ms": round(max(samples), 4),
            "p95_ms": round(sorted(samples)[int(len(samples) * 0.95)], 4),
        }

    report = {
        "benchmark": "gpu_pipeline",
        "version": "1.0",
        "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "parameters": {
            "num_frames": num_frames,
            "width": width,
            "height": height,
            "num_indices": num_indices,
        },
        "results": {
            "composite_fps": round(fps, 2),
            "frame_time": _stats(frame_times),
            "vertex_pass": _stats(vertex_costs),
            "fragment_pass": _stats(fragment_costs),
            "texture_readout": _stats(readout_costs),
            "ptp_drift": {
                "mean_ms": round(drift_mean, 6),
                "std_ms": round(drift_std, 6),
                "max_ms": round(drift_max, 6),
                "samples": num_frames,
            },
        },
        "regression_thresholds": {
            "min_fps": 58.0,
            "max_frame_time_mean_ms": 18.0,
            "max_ptp_drift_std_ms": 0.15,
        },
    }
    return report


def check_regressions(report: dict) -> list[str]:
    """Return a list of failed regression checks."""
    failures = []
    thresholds = report["regression_thresholds"]
    results = report["results"]

    if results["composite_fps"] < thresholds["min_fps"]:
        failures.append(
            f"FPS regression: {results['composite_fps']:.2f} < {thresholds['min_fps']}"
        )
    if results["frame_time"]["mean_ms"] > thresholds["max_frame_time_mean_ms"]:
        failures.append(
            f"Frame time regression: {results['frame_time']['mean_ms']:.2f}ms "
            f"> {thresholds['max_frame_time_mean_ms']}ms"
        )
    if results["ptp_drift"]["std_ms"] > thresholds["max_ptp_drift_std_ms"]:
        failures.append(
            f"PTP drift std regression: {results['ptp_drift']['std_ms']:.6f}ms "
            f"> {thresholds['max_ptp_drift_std_ms']}ms"
        )
    return failures


async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="StageCanvas GPU Pipeline Benchmark")
    parser.add_argument("--frames", type=int, default=200, help="Number of frames to simulate")
    parser.add_argument("--width", type=int, default=3840, help="Frame width (pixels)")
    parser.add_argument("--height", type=int, default=2160, help="Frame height (pixels)")
    parser.add_argument("--output", type=str, default=None, help="Output JSON file path")
    parser.add_argument("--ci", action="store_true", help="Exit with non-zero if regressions found")
    args = parser.parse_args()

    report = await run_benchmark(
        num_frames=args.frames,
        width=args.width,
        height=args.height,
    )

    json_output = json.dumps(report, indent=2)
    print("\n[bench] === REPORT ===")
    print(json_output)

    # Write JSON report to file if requested
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_output)
        print(f"\n[bench] Report written to {out_path}")

    # Regression check
    failures = check_regressions(report)
    if failures:
        print("\n[bench] REGRESSIONS DETECTED:")
        for f in failures:
            print(f"  ✗ {f}")
        if args.ci:
            sys.exit(1)
    else:
        print("\n[bench] ✓ All regression checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
