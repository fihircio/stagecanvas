from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

ORCH_ROOT = Path(__file__).resolve().parents[1]
if str(ORCH_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCH_ROOT))

from app.timeline_repository import TimelineRepository


class TimelineRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "timeline-test.db"
        self.repo = TimelineRepository(self.db_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_track_and_clip_order_is_stable(self) -> None:
        show_id = "order-show"
        self.repo.upsert_show(show_id, 90_000)
        self.repo.upsert_track(show_id, "t-video", "Video", "video", None)
        self.repo.upsert_track(show_id, "t-audio", "Audio", "audio", None)
        self.repo.upsert_clip(show_id, "t-video", "c2", "Second", 2_000, 1_000, "video", None)
        self.repo.upsert_clip(show_id, "t-video", "c1", "First", 1_000, 1_000, "video", 0)

        snapshot = self.repo.snapshot(show_id)
        self.assertEqual([t.track_id for t in snapshot.tracks], ["t-video", "t-audio"])
        self.assertEqual([c.clip_id for c in snapshot.tracks[0].clips], ["c1", "c2"])

    def test_delete_show_cascades_tracks_and_clips(self) -> None:
        show_id = "cascade-show"
        self.repo.upsert_show(show_id, 30_000)
        self.repo.upsert_track(show_id, "t1", "Main", "video", 0)
        self.repo.upsert_clip(show_id, "t1", "c1", "Clip", 0, 1_000, "video", 0)

        self.repo.delete_show(show_id)
        with self.assertRaises(KeyError):
            self.repo.snapshot(show_id)

    def test_persists_data_across_repository_reopen(self) -> None:
        show_id = "persist-show"
        self.repo.upsert_show(show_id, 45_000)
        self.repo.upsert_track(show_id, "t1", "Track", "video", 0)
        self.repo.upsert_clip(show_id, "t1", "c1", "Persisted", 5_000, 10_000, "video", 0)

        reopened = TimelineRepository(self.db_path)
        snapshot = reopened.snapshot(show_id, playhead_ms=99_000)
        self.assertEqual(snapshot.show_id, show_id)
        self.assertEqual(snapshot.playhead_ms, 45_000)
        self.assertEqual(snapshot.tracks[0].clips[0].label, "Persisted")


if __name__ == "__main__":
    unittest.main()
