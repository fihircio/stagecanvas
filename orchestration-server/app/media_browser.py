import os
from pathlib import Path
from typing import List, Dict, Any
from .models import UserRole

class MediaBrowser:
    """
    SC-115 - Local Drive Ingest & Media Browser
    Handles safe listing of local directories for media discovery.
    """
    
    # Restrict browsing to common media areas or allowed roots (can be configured via ENV)
    ALLOWED_ROOTS = [
        str(Path.home()),
        "/Volumes", # macOS external drives
        "/mnt",     # Linux mounts
    ]

    @staticmethod
    def list_directory(target_path: str) -> Dict[str, Any]:
        """
        List files and folders at the target path.
        Returns metadata about each entry.
        """
        path = Path(target_path).resolve()
        
        # Security check: must be within an allowed root
        is_safe = any(str(path).startswith(root) for root in MediaBrowser.ALLOWED_ROOTS)
        if not is_safe:
            # Fallback to home if out of bounds (or we could raise an error)
            path = Path.home()

        if not path.exists() or not path.is_dir():
            return {"path": str(path), "entries": [], "error": "NOT_A_DIRECTORY"}

        entries = []
        try:
            for entry in os.scandir(path):
                # Skip hidden files
                if entry.name.startswith('.'):
                    continue
                
                stats = entry.stat()
                entries.append({
                    "name": entry.name,
                    "path": entry.path,
                    "is_dir": entry.is_dir(),
                    "size": stats.st_size if entry.is_file() else 0,
                    "mtime": stats.st_mtime
                })
        except PermissionError:
            return {"path": str(path), "entries": [], "error": "PERMISSION_DENIED"}

        # Sort: directories first, then alphabetical
        entries.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

        return {
            "path": str(path),
            "parent": str(path.parent) if path.parent != path else None,
            "entries": entries
        }

    @staticmethod
    def is_media_file(filename: str) -> bool:
        """Simple extension-based check for media files."""
        media_exts = {'.mp4', '.mov', '.mkv', '.avi', '.mp3', '.wav', '.flac', '.png', '.jpg', '.jpeg'}
        return Path(filename).suffix.lower() in media_exts
