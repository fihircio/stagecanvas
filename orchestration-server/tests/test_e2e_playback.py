import asyncio
import os
import sys
import unittest
import tempfile
import time
from pathlib import Path
from httpx import ASGITransport, AsyncClient

# Setup path for imports
ORCH_ROOT = Path(__file__).resolve().parents[1]
if str(ORCH_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCH_ROOT))

import app.main as main_mod
from app.command_ledger import CommandLedger
from app.registry import NodeRegistry, MediaRegistry

class E2EPlaybackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        self._ledger_path = self.data_dir / "orch_e2e.db"
        self._media_registry_path = self.data_dir / "media_registry.json"
        
        # Mock globals in main_mod
        self._orig_registry = main_mod.registry
        self._orig_ledger = main_mod.command_ledger
        self._orig_media_registry = main_mod.media_registry
        
        main_mod.registry = NodeRegistry()
        main_mod.command_ledger = CommandLedger(self._ledger_path)
        main_mod.media_registry = MediaRegistry(self._media_registry_path)
        
        from app.auth import create_access_token
        token = create_access_token(data={"sub": "admin", "role": "admin"})
        self.headers = {"Authorization": f"Bearer {token}"}
        
        self.client = AsyncClient(
            transport=ASGITransport(app=main_mod.app), 
            base_url="http://testserver",
            headers=self.headers
        )
        
        # Register a dummy node
        await self.client.post("/api/v1/nodes/register", json={
            "node_id": "test-node-1",
            "label": "TEST-1",
            "capabilities": {"webrtc": True}
        })

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        main_mod.registry = self._orig_registry
        main_mod.command_ledger = self._orig_ledger
        main_mod.media_registry = self._orig_media_registry
        self._tmp.cleanup()

    async def test_full_playback_flow(self):
        """
        SC-129: E2E Playback Flow
        1. Ingest a sample MP4.
        2. Create a show/timeline (simulated via heartbeat readiness).
        3. Call POST /api/v1/operators/play.
        4. Assert command is queued for the node.
        """
        # 1. Ingest Asset
        ingest_resp = await self.client.post("/api/v1/media", json={
            "asset_id": "sample-video",
            "label": "Sample Video",
            "codec_profile": "H264",
            "duration_ms": 10000,
            "size_bytes": 5000000,
            "uri": "file:///tmp/sample.mp4"
        })
        self.assertEqual(ingest_resp.status_code, 200)
        
        # 2. Node Readiness
        hb_resp = await self.client.post("/api/v1/nodes/test-node-1/heartbeat", json={
            "version": "v1",
            "status": "READY",
            "show_id": "e2e-show",
            "position_ms": 0,
            "metrics": {"cpu_pct": 5.0, "gpu_pct": 5.0, "fps": 60.0, "dropped_frames": 0},
            "cache": {
                "show_id": "e2e-show",
                "preload_state": "READY",
                "asset_total": 1,
                "cached_assets": 1,
            }
        })
        self.assertEqual(hb_resp.status_code, 200)
        
        # 3. Trigger Play
        play_resp = await self.client.post("/api/v1/operators/play", json={
            "request_id": "play-req-1",
            "payload": {"show_id": "e2e-show"},
            "node_ids": ["test-node-1"]
        })
        self.assertEqual(play_resp.status_code, 200)
        data = play_resp.json()
        self.assertTrue(data["ok"])
        self.assertIn("play_at", data)
        self.assertEqual(data["delivered_count"] + data["queued_count"], 1)
        
        # 4. Verify command in registry
        node = await main_mod.registry.get("test-node-1")
        self.assertIsNotNone(node)
        self.assertEqual(len(node.pending_commands), 1)
        cmd = node.pending_commands[0]
        self.assertEqual(cmd["command"], "PLAY_AT")
        self.assertGreater(cmd["target_time_ms"], 0)

if __name__ == "__main__":
    unittest.main()
