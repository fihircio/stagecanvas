from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Literal

LedgerStatus = Literal["BYPASS", "RESERVED", "REPLAY", "MISMATCH", "IN_PROGRESS"]


class CommandLedger:
    """Persistent idempotency + sequence ledger for orchestration commands."""

    def __init__(self, db_path: Path, ttl_ms: int = 120_000) -> None:
        self._db_path = db_path
        self._ttl_ms = ttl_ms
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def next_seq(self) -> int:
        now = int(time.time() * 1000)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT value FROM seq_counter WHERE name = 'command_seq'").fetchone()
            if row is None:
                next_value = now
                conn.execute(
                    "INSERT INTO seq_counter(name, value) VALUES('command_seq', ?)",
                    (next_value,),
                )
            else:
                prev = int(row["value"])
                next_value = now if now > prev else (prev + 1)
                conn.execute(
                    "UPDATE seq_counter SET value = ? WHERE name = 'command_seq'",
                    (next_value,),
                )
            conn.commit()
            return next_value

    def begin_request(
        self,
        scope: str,
        request_id: str | None,
        payload: dict[str, Any],
    ) -> tuple[LedgerStatus, dict[str, Any] | None]:
        if not request_id:
            return "BYPASS", None

        self._cleanup()
        payload_hash = self._hash_payload(payload)
        now = int(time.time() * 1000)

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT request_hash, response_json
                FROM command_idempotency
                WHERE scope = ? AND request_id = ?
                """,
                (scope, request_id),
            ).fetchone()

            if row is None:
                conn.execute(
                    """
                    INSERT INTO command_idempotency(scope, request_id, request_hash, response_json, created_ms, updated_ms)
                    VALUES(?, ?, ?, NULL, ?, ?)
                    """,
                    (scope, request_id, payload_hash, now, now),
                )
                conn.commit()
                return "RESERVED", None

            if row["request_hash"] != payload_hash:
                conn.commit()
                return "MISMATCH", None

            response_json = row["response_json"]
            if response_json is None:
                conn.commit()
                return "IN_PROGRESS", None

            replay = json.loads(response_json)
            replay["idempotent_replay"] = True
            replay["reason_code"] = "DUPLICATE_REQUEST"
            conn.commit()
            return "REPLAY", replay

    def finalize_request(
        self,
        scope: str,
        request_id: str | None,
        response_payload: dict[str, Any],
    ) -> None:
        if not request_id:
            return
        now = int(time.time() * 1000)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE command_idempotency
                SET response_json = ?, updated_ms = ?
                WHERE scope = ? AND request_id = ?
                """,
                (json.dumps(response_payload, separators=(",", ":"), sort_keys=True), now, scope, request_id),
            )
            conn.commit()

    def _cleanup(self) -> None:
        now = int(time.time() * 1000)
        cutoff = now - self._ttl_ms
        with self._connect() as conn:
            conn.execute("DELETE FROM command_idempotency WHERE updated_ms < ?", (cutoff,))
            conn.commit()

    def _hash_payload(self, payload: dict[str, Any]) -> str:
        serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS seq_counter (
                  name TEXT PRIMARY KEY,
                  value INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS command_idempotency (
                  scope TEXT NOT NULL,
                  request_id TEXT NOT NULL,
                  request_hash TEXT NOT NULL,
                  response_json TEXT,
                  created_ms INTEGER NOT NULL,
                  updated_ms INTEGER NOT NULL,
                  PRIMARY KEY(scope, request_id)
                );
                """
            )
            conn.commit()

