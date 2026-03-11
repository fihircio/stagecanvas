import subprocess
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class MetadataExtractor:
    """
    SC-116 - Automated Thumbnail & Metadata Extraction
    Uses ffprobe and ffmpeg to analyze media and generate visual previews.
    """

    @staticmethod
    def get_metadata(file_path: str) -> Dict[str, Any]:
        """
        Extract technical specs using ffprobe.
        """
        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            format_info = data.get("format", {})
            streams = data.get("streams", [])
            
            # Find the first video stream
            video_stream: Dict[str, Any] = next((s for s in streams if s.get("codec_type") == "video"), {})
            
            return {
                "duration_ms": int(float(format_info.get("duration", 0))),
                "size_bytes": int(format_info.get("size", 0)),
                "bitrate_bps": int(format_info.get("bit_rate", 0)),
                "codec": str(video_stream.get("codec_name", "unknown")),
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "fps": MetadataExtractor._parse_fps(str(video_stream.get("avg_frame_rate", "0/0"))),
            }
        except Exception as e:
            logger.error(f"Failed to extract metadata for {file_path}: {e}")
            return {}

    @staticmethod
    def generate_thumbnail(file_path: str, output_path: str, timestamp_ms: int = 1000) -> bool:
        """
        Generate a JPG thumbnail from the video at a specific timestamp.
        """
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            cmd = [
                "ffmpeg",
                "-ss", str(timestamp_ms / 1000.0), # Seek to timestamp
                "-i", file_path,
                "-frames:v", "1", # Capture one frame
                "-q:v", "2",      # High quality
                "-vf", "scale=640:-1", # Resize width to 640, preserve aspect ratio
                "-y",              # Overwrite
                output_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except Exception as e:
            logger.error(f"Failed to generate thumbnail for {file_path}: {e}")
            return False

    @staticmethod
    def _parse_fps(fps_str: str) -> float:
        """Parses avg_frame_rate string like '30000/1001' into float."""
        try:
            if "/" in fps_str:
                num, den = map(int, fps_str.split("/"))
                if den == 0: return 0.0
                return round(num / den, 3)
            return float(fps_str)
        except (ValueError, ZeroDivisionError):
            return 0.0
