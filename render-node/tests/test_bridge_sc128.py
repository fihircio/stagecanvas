import asyncio
import unittest
from unittest.mock import MagicMock
from app.bridge import MockUnityBridge

class TestBridgeSC128(unittest.IsolatedAsyncioTestCase):
    async def test_play_clip(self):
        bridge = MockUnityBridge()
        
        # We need a consumer to drain the queue to avoid hanging
        async def consumer():
            msg = await bridge._queue.get()
            return msg

        consumer_task = asyncio.create_task(consumer())
        await bridge.play_clip("sample_asset_123", 5000)
        
        result = await consumer_task
        self.assertIn('"event": "play_clip"', result)
        self.assertIn('"asset_id": "sample_asset_123"', result)
        self.assertIn('"start_time_ms": 5000', result)

    async def test_seek(self):
        bridge = MockUnityBridge()
        
        async def consumer():
            msg = await bridge._queue.get()
            return msg

        consumer_task = asyncio.create_task(consumer())
        await bridge.seek(12000)
        
        result = await consumer_task
        self.assertIn('"event": "seek"', result)
        self.assertIn('"position_ms": 12000', result)

if __name__ == '__main__':
    unittest.main()
