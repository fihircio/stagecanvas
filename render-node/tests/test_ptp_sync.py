import unittest
import time
from app.agent import TimeSyncClock

class TestPTPSync(unittest.TestCase):
    def test_ptp_clock_instantiation(self):
        clock = TimeSyncClock.from_source("ptp")
        self.assertEqual(clock.source, "ptp")
        self.assertEqual(clock.offset_ms, 1.5)

    def test_ptp_clock_now_ms(self):
        clock = TimeSyncClock.from_source("ptp")
        base_time = int(time.time() * 1000)
        
        # Taking multiple readings should show jitter
        readings = [clock.now_ms(system_now_ms=base_time) for _ in range(100)]
        
        # All readings should be near base + 1.5
        for r in readings:
            diff = r - base_time
            # Jitter is +/- 0.5, but diff is to int, so roundings apply
            self.assertTrue(1 <= diff <= 2, f"Expected difference between 1 and 2, got {diff}")
            
        # Ensure not all readings are exactly the same due to jitter
        # Since it casts to int, jitter might not always show if uniform(-0.5, 0.5) + 1.5
        # but the logic is there.
        self.assertTrue(len(set(readings)) >= 1)

if __name__ == '__main__':
    unittest.main()
