import logging
import os
import time
import json
import gzip
import shutil
from datetime import datetime
from logging.handlers import RotatingFileHandler
from collections import deque
from typing import Any, Dict, List, Optional

class ShowLogger:
    """
    Millisecond-accurate logger for show operations (SC-124).
    Handles rotation, compression, and real-time broadcasting via WebSocket.
    """
    def __init__(self, log_dir: str, filename: str = "show_operations.log", max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.log_path = os.path.join(log_dir, filename)
        
        # In-memory buffer for live terminal streaming (last 100 entries)
        self.live_buffer = deque(maxlen=100)
        self.callbacks = []
        
        # Setup File Logger with rotation
        self.logger = logging.getLogger("show_ops")
        self.logger.setLevel(logging.INFO)
        
        # Custom formatter with millisecond precision
        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        self.handler = RotatingFileHandler(
            self.log_path, 
            maxBytes=max_bytes, 
            backupCount=backup_count
        )
        self.handler.setFormatter(formatter)
        
        # SC-124: Custom rotation hook for compression
        self.handler.rotator = self._rotate_and_compress
        self.handler.namer = self._name_compressed_file
        
        self.logger.addHandler(self.handler)

    def _name_compressed_file(self, name: str) -> str:
        return name + ".gz"

    def _rotate_and_compress(self, source: str, dest: str):
        with open(source, 'rb') as f_in:
            with gzip.open(dest, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(source)

    def log(self, level: str, event_type: str, message: str, detail: Optional[Dict[str, Any]] = None):
        """Standardized log entry for show events."""
        timestamp = datetime.now().isoformat(timespec='milliseconds')
        entry = {
            "timestamp": timestamp,
            "level": level.upper(),
            "event": event_type.upper(),
            "message": message,
            "detail": detail or {}
        }
        
        log_str = json.dumps(entry)
        if level.lower() == "info":
            self.logger.info(log_str)
        elif level.lower() == "warn" or level.lower() == "warning":
            self.logger.warning(log_str)
        elif level.lower() == "error":
            self.logger.error(log_str)
            
        self.live_buffer.append(entry)
        for cb in self.callbacks:
            try:
                cb(entry)
            except Exception:
                pass

    def add_callback(self, cb):
        self.callbacks.append(cb)

    def remove_callback(self, cb):
        if cb in self.callbacks:
            self.callbacks.remove(cb)

    def log_cue(self, show_id: str, cue_id: str, payload: Dict[str, Any]):
        self.log("INFO", "CUE_FIRE", f"Cue fired: {cue_id} in show {show_id}", {"show_id": show_id, "cue_id": cue_id, "payload": payload})

    def log_swap(self, node_id: str, layer_id: str, asset_id: str):
        self.log("INFO", "HOT_SWAP", f"Hot-swap complete on {node_id}: {layer_id} -> {asset_id}", {"node_id": node_id, "layer_id": layer_id, "asset_id": asset_id})

    def log_drift(self, node_id: str, drift_ms: float, level: str):
        self.log(level, "PTP_DRIFT", f"Node {node_id} drift: {drift_ms:.3f}ms", {"node_id": node_id, "drift_ms": drift_ms, "ptp_status": level})

    def get_live_logs(self) -> List[Dict[str, Any]]:
        return list(self.live_buffer)

    def get_log_file_list(self) -> List[str]:
        return [f for f in os.listdir(self.log_dir) if f.startswith("show_operations")]

    def get_log_content(self, filename: str) -> bytes:
        path = os.path.join(self.log_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Log file not found: {filename}")
        
        with open(path, 'rb') as f:
            return f.read()
