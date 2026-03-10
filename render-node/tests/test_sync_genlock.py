import unittest
import asyncio
import time
from render_node.app.sync_genlock import GenlockSync

class TestGenlockSync(unittest.TestCase):
    def test_genlock_metrics_initial(self):
        genlock = GenlockSync()
        metrics = genlock.get_metrics()
        self.assertEqual(metrics["genlock_total_hold_ms"], 0.0)
        self.assertTrue(metrics["genlock_active"])

    def test_genlock_wait(self):
        # We need to run this in an event loop
        async def run_test():
            genlock = GenlockSync(target_fps=100.0) # 10ms interval
            
            # First wait should hold for some time or return immediately if pulse aligns
            hold_ms = await genlock.wait_for_pulse()
            self.assertGreaterEqual(hold_ms, 0.0)
            
            metrics = genlock.get_metrics()
            self.assertEqual(metrics["genlock_total_hold_ms"], hold_ms)

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
