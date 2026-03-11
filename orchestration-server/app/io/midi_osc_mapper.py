import sqlite3
import uuid
import time
import asyncio
from typing import Callable, Any, Awaitable
from pathlib import Path

from ..models import MappingEntry, LearnRequest, ControlCommand
from ..config import PROTOCOL_VERSION

class MidiOscMapper:
    def __init__(self, db_path: Path, dispatch_callback: Callable[[ControlCommand], Awaitable[None]]):
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._dispatch_callback = dispatch_callback
        self.active_learn_request: LearnRequest | None = None
        self._init_db()
        self._mappings: dict[str, MappingEntry] = self._load_mappings()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS io_mappings (
                    mapping_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_address TEXT NOT NULL,
                    target_layer_id TEXT NOT NULL,
                    target_property TEXT NOT NULL,
                    min_val REAL NOT NULL DEFAULT 0.0,
                    max_val REAL NOT NULL DEFAULT 1.0,
                    UNIQUE(source_type, source_address)
                );
                """
            )
            conn.commit()

    def _load_mappings(self) -> dict[str, MappingEntry]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM io_mappings").fetchall()
            return {
                f"{row['source_type']}:{row['source_address']}": MappingEntry(
                    mapping_id=row['mapping_id'],
                    source_type=row['source_type'],
                    source_address=row['source_address'],
                    target_layer_id=row['target_layer_id'],
                    target_property=row['target_property'],
                    min_val=row['min_val'],
                    max_val=row['max_val']
                ) for row in rows
            }

    def start_learning(self, target_layer_id: str, target_property: str):
        self.active_learn_request = LearnRequest(
            target_layer_id=target_layer_id,
            target_property=target_property
        )

    def stop_learning(self):
        self.active_learn_request = None

    def get_mappings(self) -> list[MappingEntry]:
        return list(self._mappings.values())

    async def handle_signal(self, source_type: str, source_address: str, value: float):
        # Learn mode
        if self.active_learn_request:
            mapping_id = str(uuid.uuid4())
            req = self.active_learn_request
            entry = MappingEntry(
                mapping_id=mapping_id,
                source_type=source_type,
                source_address=source_address,
                target_layer_id=req.target_layer_id,
                target_property=req.target_property,
                min_val=0.0,
                max_val=1.0
            )
            
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO io_mappings (mapping_id, source_type, source_address, target_layer_id, target_property, min_val, max_val)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_type, source_address) DO UPDATE SET
                        target_layer_id=excluded.target_layer_id,
                        target_property=excluded.target_property
                    """,
                    (entry.mapping_id, entry.source_type, entry.source_address, entry.target_layer_id, entry.target_property, entry.min_val, entry.max_val)
                )
                conn.commit()
            
            self._mappings[f"{source_type}:{source_address}"] = entry
            self.active_learn_request = None
            print(f"[mapper] Learned {source_type}:{source_address} -> {req.target_layer_id}.{req.target_property}")
            return

        # Mapping mode
        key = f"{source_type}:{source_address}"
        if key in self._mappings:
            entry = self._mappings[key]
            # Map value (0.0 - 1.0) to (min_val - max_val)
            mapped_val = entry.min_val + (value * (entry.max_val - entry.min_val))
            
            # Send command
            cmd = ControlCommand(
                version=PROTOCOL_VERSION,
                command="UPDATE_LAYERS",
                payload={
                    "updates": [
                        {
                            "layer_id": entry.target_layer_id,
                            "properties": {
                                entry.target_property: mapped_val
                            }
                        }
                    ]
                },
                seq=0, # In a real implementation we'd get the actual seq, but for realtime mapped updates 0 might suffice or they bypass seq
                origin="operator"
            )
            await self._dispatch_callback(cmd)
