import asyncio
import unittest
import time
from unittest.mock import MagicMock, patch
from app.cluster_manager import ClusterManager

class TestFailover(unittest.IsolatedAsyncioTestCase):
    async def test_backup_promotion(self):
        # Initialize as BACKUP
        # We'll mock the HTTP response to fail
        manager = ClusterManager(
            role="BACKUP", 
            primary_url="http://primary:8000", 
            heartbeat_interval=0.1, 
            failover_timeout=0.3
        )
        
        # We want httpx.AsyncClient.get to raise an exception or return non-200
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = Exception("Primary Down")
            
            start_time = time.time()
            await manager.start()
            
            # Wait for promotion - should happen around 0.3s + some overhead
            # We'll wait up to 1 second
            for _ in range(10):
                await asyncio.sleep(0.1)
                if manager.role == "PRIMARY":
                    break
            
            end_time = time.time()
            await manager.stop()
            
            self.assertEqual(manager.role, "PRIMARY")
            self.assertLess(end_time - start_time, 2.0) # Should be fast

    async def test_primary_stays_primary(self):
        manager = ClusterManager(role="PRIMARY")
        await manager.start()
        self.assertEqual(manager.role, "PRIMARY")
        await asyncio.sleep(0.2)
        self.assertEqual(manager.role, "PRIMARY")
        await manager.stop()

if __name__ == '__main__':
    unittest.main()
