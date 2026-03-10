from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.state import NodeState


class CachePersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_cache_persists_and_restores(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "cache.json"
            state = NodeState(node_id="n1", label="Node 1", cache_index_path=cache_path)
            state.cache_index.add("asset-a", 1024, now_ms=100)
            state.cache_index.add("asset-b", 2048, now_ms=110)
            state._persist_cache_index()

            restored = NodeState(node_id="n1", label="Node 1", cache_index_path=cache_path)
            assets = [entry.asset_id for entry in restored.cache_index.list_assets()]
            self.assertEqual(assets, ["asset-a", "asset-b"])
            self.assertEqual(restored.cache_index.current_bytes, 3072)


if __name__ == "__main__":
    unittest.main()
