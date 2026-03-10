from __future__ import annotations

import unittest

from app.state import CacheIndex


class CacheIndexTests(unittest.TestCase):
    def test_eviction_lru(self) -> None:
        cache = CacheIndex(max_bytes=100)
        cache.add("a", 40, now_ms=100)
        cache.add("b", 40, now_ms=110)
        cache.add("c", 30, now_ms=120)

        # total 110 -> should evict oldest (a)
        assets = [entry.asset_id for entry in cache.list_assets()]
        self.assertNotIn("a", assets)
        self.assertIn("b", assets)
        self.assertIn("c", assets)
        self.assertLessEqual(cache.current_bytes, cache.max_bytes)

    def test_touch_moves_to_recent(self) -> None:
        cache = CacheIndex(max_bytes=100)
        cache.add("a", 40, now_ms=100)
        cache.add("b", 40, now_ms=110)
        cache.touch("a", now_ms=120)
        cache.add("c", 30, now_ms=130)

        assets = [entry.asset_id for entry in cache.list_assets()]
        # b should be evicted because a was touched most recently
        self.assertNotIn("b", assets)
        self.assertIn("a", assets)
        self.assertIn("c", assets)


if __name__ == "__main__":
    unittest.main()
