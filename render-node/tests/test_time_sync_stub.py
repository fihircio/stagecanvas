from __future__ import annotations

import unittest

from app.agent import TimeSyncClock


class TimeSyncStubTests(unittest.TestCase):
    def test_default_time_sync_is_system(self) -> None:
        clock = TimeSyncClock.from_source("system")
        self.assertEqual(clock.source, "system")
        self.assertEqual(clock.drift_ms(1000), 0.0)

    def test_ntp_and_ptp_defaults(self) -> None:
        ntp = TimeSyncClock.from_source("ntp")
        ptp = TimeSyncClock.from_source("ptp")
        self.assertEqual(ntp.source, "ntp")
        self.assertEqual(ptp.source, "ptp")
        self.assertNotEqual(ntp.drift_ms(0), 0.0)
        self.assertNotEqual(ptp.drift_ms(0), 0.0)

    def test_override_offset(self) -> None:
        clock = TimeSyncClock.from_source("ntp", offset_ms=7.5)
        self.assertEqual(clock.drift_ms(0), 7.5)
        self.assertEqual(clock.now_ms(1000), 1007)


if __name__ == "__main__":
    unittest.main()
