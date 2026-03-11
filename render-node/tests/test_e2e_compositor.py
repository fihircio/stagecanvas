import asyncio
import unittest
import time
from pathlib import Path
import sys
from unittest.mock import MagicMock

# Setup path for imports
RENDER_ROOT = Path(__file__).resolve().parents[1]
if str(RENDER_ROOT) not in sys.path:
    sys.path.insert(0, str(RENDER_ROOT))

from app.state import NodeState
from app.bridge import NullRendererBridge, NullDecoder

class E2ECompositorTests(unittest.IsolatedAsyncioTestCase):
    async def test_compositor_visual_output_flow(self):
        """
        SC-129: Render Node E2E Compositor Test
        Assert that PLAY_AT -> tick -> production of frames actually happens.
        """
        # 1. Setup State with a real-ish sequence
        bridge = NullRendererBridge()
        decoder = NullDecoder()
        state = NodeState(node_id="test-render-1", label="RENDER-1", bridge=bridge, decoder=decoder)
        
        # 2. Add a Video Layer (simulated mock)
        layer = MagicMock()
        layer.layer_id = "layer-1"
        # In a real scenario, the bridge/renderer would hold this. 
        # Here we test the state machine's transition and timing.
        
        # 3. Apply PLAY_AT command
        now_ms = int(time.time() * 1000)
        target_time_ms = now_ms + 100
        
        await state.apply_command(
            command="PLAY_AT",
            seq=1,
            payload={"show_id": "test-show", "assets": []},
            target_time_ms=target_time_ms
        )
        
        self.assertEqual(state.status, "READY") # Still waiting for target time
        self.assertEqual(state.scheduled_play_time_ms, target_time_ms)
        
        # 4. Wait for target time and tick
        await asyncio.sleep(0.15)
        # Tick multiple times to cross the 33ms threshold and advance position
        for _ in range(5):
            await state.tick(33.3)
        
        self.assertEqual(state.status, "PLAYING")
        self.assertGreater(state.playback_frames_emitted, 0)
        self.assertGreater(state.position_ms, 0)
        
        # 5. Verify seek
        await state.apply_command(
            command="SEEK",
            seq=2,
            payload={"position_ms": 5000},
            target_time_ms=None
        )
        self.assertEqual(state.position_ms, 5000.0)

if __name__ == "__main__":
    unittest.main()
