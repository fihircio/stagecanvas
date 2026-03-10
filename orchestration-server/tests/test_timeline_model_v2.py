from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

ORCH_ROOT = Path(__file__).resolve().parents[1]
if str(ORCH_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCH_ROOT))

from app.timeline_repository import TimelineRepository
from app.models import TimelineLayer, TimelineLayerTransform


class TimelineModelV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "timeline-v2-test.db"
        self.repo = TimelineRepository(self.db_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_upsert_clip_with_layers_and_offset(self) -> None:
        show_id = "v2-show"
        self.repo.upsert_show(show_id, 60_000)
        self.repo.upsert_track(show_id, "t1", "Main", "video", 0)
        
        layers = [
            TimelineLayer(
                layer_id="l1",
                label="Base",
                asset_id="asset-1",
                opacity=0.8,
                blend_mode="normal",
                transform=TimelineLayerTransform(x=10, y=20, scale_x=1.5, scale_y=1.5)
            ),
            TimelineLayer(
                layer_id="l2",
                label="Overlay",
                asset_id="asset-2",
                opacity=1.0,
                blend_mode="screen",
                transform=TimelineLayerTransform(x=0, y=0, scale_x=1.0, scale_y=1.0)
            )
        ]
        
        self.repo.upsert_clip(
            show_id=show_id,
            track_id="t1",
            clip_id="c1",
            label="V2 Clip",
            start_ms=1000,
            duration_ms=5000,
            kind="video",
            position=0,
            offset_ms=500,
            layers=layers
        )

        snapshot = self.repo.snapshot(show_id)
        clip = snapshot.tracks[0].clips[0]
        
        self.assertEqual(clip.clip_id, "c1")
        self.assertEqual(clip.offset_ms, 500)
        self.assertEqual(len(clip.layers), 2)
        
        l1 = clip.layers[0]
        self.assertEqual(l1.layer_id, "l1")
        self.assertEqual(l1.asset_id, "asset-1")
        self.assertAlmostEqual(l1.opacity, 0.8)
        self.assertEqual(l1.blend_mode, "normal")
        self.assertEqual(l1.transform.x, 10)
        self.assertEqual(l1.transform.scale_x, 1.5)
        
        l2 = clip.layers[1]
        self.assertEqual(l2.layer_id, "l2")
        self.assertEqual(l2.blend_mode, "screen")

    def test_update_clip_layers_clears_old_ones(self) -> None:
        show_id = "v2-update"
        self.repo.upsert_show(show_id, 60_000)
        self.repo.upsert_track(show_id, "t1", "Main", "video", 0)
        
        self.repo.upsert_clip(
            show_id=show_id,
            track_id="t1",
            clip_id="c1",
            label="Initial",
            start_ms=0,
            duration_ms=1000,
            kind="video",
            position=0,
            layers=[TimelineLayer(layer_id="old", label="Old")]
        )
        
        # Update with new layer
        self.repo.upsert_clip(
            show_id=show_id,
            track_id="t1",
            clip_id="c1",
            label="Updated",
            start_ms=0,
            duration_ms=1000,
            kind="video",
            position=0,
            layers=[TimelineLayer(layer_id="new", label="New")]
        )
        
        snapshot = self.repo.snapshot(show_id)
        clip = snapshot.tracks[0].clips[0]
        self.assertEqual(len(clip.layers), 1)
        self.assertEqual(clip.layers[0].layer_id, "new")

    def test_delete_track_cascades_to_layers(self) -> None:
        show_id = "v2-cascade"
        self.repo.upsert_show(show_id, 60_000)
        self.repo.upsert_track(show_id, "t1", "Main", "video", 0)
        self.repo.upsert_clip(
            show_id=show_id,
            track_id="t1",
            clip_id="c1",
            label="Clip",
            start_ms=0,
            duration_ms=1000,
            kind="video",
            position=0,
            layers=[TimelineLayer(layer_id="l1", label="L1")]
        )
        
        # Verify layer exists in DB (direct check if we wanted, but snapshot works)
        snapshot = self.repo.snapshot(show_id)
        self.assertEqual(len(snapshot.tracks[0].clips[0].layers), 1)
        
        self.repo.delete_track(show_id, "t1")
        
        # Re-add track and clip without layers to ensure it's empty
        self.repo.upsert_track(show_id, "t1", "Main", "video", 0)
        self.repo.upsert_clip(show_id, "t1", "c1", "Clip", 0, 1000, "video", 0)
        
        snapshot = self.repo.snapshot(show_id)
        self.assertEqual(len(snapshot.tracks[0].clips[0].layers), 0)


if __name__ == "__main__":
    unittest.main()
