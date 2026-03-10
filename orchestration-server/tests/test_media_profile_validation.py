from __future__ import annotations

import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

ORCH_ROOT = Path(__file__).resolve().parents[1]
if str(ORCH_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCH_ROOT))

from app.models import MediaAssetCreateRequest


class MediaProfileValidationTests(unittest.TestCase):
    def test_supported_codec_profiles_accept(self) -> None:
        profiles = ["HAP", "HAP-Q", "ProRes4444", "H264", "hap", "prores4444", "h264-main"]
        for profile in profiles:
            asset = MediaAssetCreateRequest(
                asset_id="asset-1",
                label="Asset",
                codec_profile=profile,
                duration_ms=0,
                size_bytes=10,
            )
            normalized = asset.codec_profile.upper().replace("_", "-").replace(" ", "-")
            if normalized == "H264-MAIN":
                normalized = "H264"
            self.assertIn(normalized, ["HAP", "HAP-Q", "PRORES4444", "H264", "H265"])

    def test_unsupported_codec_profile_rejected(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            MediaAssetCreateRequest(
                asset_id="asset-2",
                label="Asset",
                codec_profile="VP9",
                duration_ms=0,
                size_bytes=10,
            )
        self.assertIn("UNSUPPORTED_CODEC_PROFILE", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
