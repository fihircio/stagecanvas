from __future__ import annotations

import asyncio
import time
import unittest
from pathlib import Path
import sys

RENDER_ROOT = Path(__file__).resolve().parents[1]
if str(RENDER_ROOT) not in sys.path:
    sys.path.insert(0, str(RENDER_ROOT))

from app.agent import RenderNodeAgent
from app.state import NodeState
from app.bridge import NullRendererBridge


class PrecisionSchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_scheduler_drift_performance(self) -> None:
        # Test drift over 2 seconds of 60fps playback
        agent = RenderNodeAgent(
            base_url="http://localhost:8010",
            node_id="perf-node",
            label="Perf Node",
            tick_interval_sec=0.0166, # ~60fps
        )
        
        # Start playback manually
        await agent.state.apply_command("PLAY_AT", 1, {"show_id": "test"}, target_time_ms=None)
        
        # Run the loop for a bit
        playback_task = asyncio.create_task(agent.playback_loop())
        
        # Monitor drift for 2 seconds
        start_time = time.time()
        max_drift = 0.0
        while time.time() - start_time < 2.0:
            await asyncio.sleep(0.1)
            max_drift = max(max_drift, abs(agent.state.drift_ms))
            
        agent._stop_event.set()
        await playback_task
        
        print(f"\n[SC-074] Max drift observed: {max_drift:.4f} ms")
        self.assertLess(max_drift, 2.0, f"Drift exceeded 2ms: {max_drift:.4f}ms")

    async def test_scheduled_play_at_precision(self) -> None:
        # Test how accurately PLAY_AT triggers
        agent = RenderNodeAgent(
            base_url="http://localhost:8010",
            node_id="sync-node",
            label="Sync Node",
            tick_interval_sec=0.005, # High frequency for testing
        )
        
        now_ms = time.time() * 1000
        target_ms = now_ms + 500 # 500ms in future
        
        await agent.state.apply_command("PLAY_AT", 1, {"show_id": "test"}, target_time_ms=target_ms)
        
        playback_task = asyncio.create_task(agent.playback_loop())
        
        # Wait until it starts
        start_wait = time.time()
        while agent.state.status != "PLAYING" and time.time() - start_wait < 1.0:
            await asyncio.sleep(0.001)
            
        actual_start_ms = time.time() * 1000
        trigger_error = actual_start_ms - target_ms
        
        agent._stop_event.set()
        await playback_task
        
        print(f"[SC-074] PLAY_AT trigger error: {trigger_error:.4f} ms")
        self.assertLess(abs(trigger_error), 20.0, f"Trigger error too high: {trigger_error:.4f}ms")


if __name__ == "__main__":
    unittest.main()
