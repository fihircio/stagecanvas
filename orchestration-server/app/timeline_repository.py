from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import MappingConfig, TimelineClip, TimelineLayer, TimelineShowSummary, TimelineSnapshotResponse, TimelineTrack


class TimelineRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._seed_demo_show()

    def list_shows(self) -> list[TimelineShowSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.show_id, s.duration_ms, COUNT(t.track_id) AS track_count
                FROM shows s
                LEFT JOIN tracks t ON t.show_id = s.show_id
                GROUP BY s.show_id, s.duration_ms
                ORDER BY s.show_id
                """
            ).fetchall()
        return [
            TimelineShowSummary(show_id=row["show_id"], duration_ms=row["duration_ms"], track_count=row["track_count"])
            for row in rows
        ]

    def upsert_show(self, show_id: str, duration_ms: int, mapping_config: dict[str, object] | None = None) -> None:
        mapping_json = None
        if mapping_config is not None:
            mapping_json = json.dumps(mapping_config, separators=(",", ":"), sort_keys=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO shows(show_id, duration_ms, mapping_config_json)
                VALUES(?, ?, ?)
                ON CONFLICT(show_id) DO UPDATE SET
                  duration_ms = excluded.duration_ms,
                  mapping_config_json = COALESCE(excluded.mapping_config_json, mapping_config_json)
                """,
                (show_id, duration_ms, mapping_json),
            )
            conn.commit()

    def delete_show(self, show_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM clips WHERE show_id = ?", (show_id,))
            conn.execute("DELETE FROM tracks WHERE show_id = ?", (show_id,))
            deleted = conn.execute("DELETE FROM shows WHERE show_id = ?", (show_id,)).rowcount
            conn.commit()
        if deleted == 0:
            raise KeyError(f"Show not found: {show_id}")

    def get_mapping_config(self, show_id: str) -> dict[str, object] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT mapping_config_json FROM shows WHERE show_id = ?",
                (show_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Show not found: {show_id}")
            raw = row["mapping_config_json"]
            if not raw:
                return None
            return json.loads(raw)

    def upsert_track(self, show_id: str, track_id: str, label: str, kind: str, position: int | None) -> None:
        with self._connect() as conn:
            if not self._show_exists(conn, show_id):
                raise KeyError(f"Show not found: {show_id}")
            resolved_position = position if position is not None else self._next_track_position(conn, show_id)
            conn.execute(
                """
                INSERT INTO tracks(show_id, track_id, label, kind, position)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(show_id, track_id)
                DO UPDATE SET label = excluded.label, kind = excluded.kind, position = excluded.position
                """,
                (show_id, track_id, label, kind, resolved_position),
            )
            conn.commit()

    def delete_track(self, show_id: str, track_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM clips WHERE show_id = ? AND track_id = ?", (show_id, track_id))
            deleted = conn.execute(
                "DELETE FROM tracks WHERE show_id = ? AND track_id = ?",
                (show_id, track_id),
            ).rowcount
            conn.commit()
        if deleted == 0:
            raise KeyError(f"Track not found: {show_id}/{track_id}")

    def upsert_clip(
        self,
        show_id: str,
        track_id: str,
        clip_id: str,
        label: str,
        start_ms: int,
        duration_ms: int,
        kind: str,
        position: int | None,
        offset_ms: int | None = None,
        layers: list[TimelineLayer] | None = None,
    ) -> None:
        with self._connect() as conn:
            if not self._track_exists(conn, show_id, track_id):
                raise KeyError(f"Track not found: {show_id}/{track_id}")
            resolved_position = position if position is not None else self._next_clip_position(conn, show_id, track_id)
            resolved_offset = offset_ms if offset_ms is not None else 0
            conn.execute(
                """
                INSERT INTO clips(show_id, track_id, clip_id, label, start_ms, duration_ms, kind, position, offset_ms)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(show_id, track_id, clip_id)
                DO UPDATE SET
                  label = excluded.label,
                  start_ms = excluded.start_ms,
                  duration_ms = excluded.duration_ms,
                  kind = excluded.kind,
                  position = excluded.position,
                  offset_ms = excluded.offset_ms
                """,
                (
                    show_id,
                    track_id,
                    clip_id,
                    label,
                    start_ms,
                    duration_ms,
                    kind,
                    resolved_position,
                    resolved_offset,
                ),
            )
            if layers is not None:
                conn.execute(
                    "DELETE FROM layers WHERE show_id = ? AND track_id = ? AND clip_id = ?",
                    (show_id, track_id, clip_id),
                )
                for i, layer in enumerate(layers):
                    transform_json = layer.transform.model_dump_json()
                    conn.execute(
                        """
                        INSERT INTO layers(show_id, track_id, clip_id, layer_id, label, asset_id, opacity, blend_mode, transform_json, position)
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            show_id,
                            track_id,
                            clip_id,
                            layer.layer_id,
                            layer.label,
                            layer.asset_id,
                            layer.opacity,
                            layer.blend_mode,
                            transform_json,
                            i,
                        ),
                    )
            conn.commit()

    def delete_clip(self, show_id: str, track_id: str, clip_id: str) -> None:
        with self._connect() as conn:
            deleted = conn.execute(
                "DELETE FROM clips WHERE show_id = ? AND track_id = ? AND clip_id = ?",
                (show_id, track_id, clip_id),
            ).rowcount
            conn.commit()
        if deleted == 0:
            raise KeyError(f"Clip not found: {show_id}/{track_id}/{clip_id}")

    def snapshot(self, show_id: str, playhead_ms: int = 0) -> TimelineSnapshotResponse:
        with self._connect() as conn:
            show = conn.execute(
                "SELECT show_id, duration_ms, mapping_config_json FROM shows WHERE show_id = ?",
                (show_id,),
            ).fetchone()
            if show is None:
                raise KeyError(f"Show not found: {show_id}")

            tracks_rows = conn.execute(
                """
                SELECT track_id, label, kind
                FROM tracks
                WHERE show_id = ?
                ORDER BY position, track_id
                """,
                (show_id,),
            ).fetchall()

            tracks: list[TimelineTrack] = []
            for track in tracks_rows:
                clip_rows = conn.execute(
                    """
                    SELECT clip_id, label, start_ms, duration_ms, kind, offset_ms
                    FROM clips
                    WHERE show_id = ? AND track_id = ?
                    ORDER BY position, clip_id
                    """,
                    (show_id, track["track_id"]),
                ).fetchall()
                clips = []
                for row in clip_rows:
                    layer_rows = conn.execute(
                        """
                        SELECT layer_id, label, asset_id, opacity, blend_mode, transform_json
                        FROM layers
                        WHERE show_id = ? AND track_id = ? AND clip_id = ?
                        ORDER BY position, layer_id
                        """,
                        (show_id, track["track_id"], row["clip_id"]),
                    ).fetchall()
                    layers = [
                        TimelineLayer(
                            layer_id=l["layer_id"],
                            label=l["label"],
                            asset_id=l["asset_id"],
                            opacity=l["opacity"],
                            blend_mode=l["blend_mode"],
                            transform=json.loads(l["transform_json"]) if l["transform_json"] else {},
                        )
                        for l in layer_rows
                    ]
                    clips.append(
                        TimelineClip(
                            clip_id=row["clip_id"],
                            label=row["label"],
                            start_ms=row["start_ms"],
                            duration_ms=row["duration_ms"],
                            offset_ms=row["offset_ms"],
                            kind=row["kind"],
                            layers=layers,
                        )
                    )
                tracks.append(
                    TimelineTrack(
                        track_id=track["track_id"],
                        label=track["label"],
                        kind=track["kind"],
                        clips=clips,
                    )
                )

            duration_ms = int(show["duration_ms"])
            mapping_config = None
            raw_mapping = show["mapping_config_json"]
            if raw_mapping:
                mapping_config = MappingConfig.model_validate(json.loads(raw_mapping))
            return TimelineSnapshotResponse(
                show_id=show["show_id"],
                duration_ms=duration_ms,
                playhead_ms=max(0, min(playhead_ms, duration_ms)),
                tracks=tracks,
                mapping_config=mapping_config,
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS shows (
                  show_id TEXT PRIMARY KEY,
                  duration_ms INTEGER NOT NULL CHECK(duration_ms > 0),
                  mapping_config_json TEXT
                );

                CREATE TABLE IF NOT EXISTS tracks (
                  show_id TEXT NOT NULL,
                  track_id TEXT NOT NULL,
                  label TEXT NOT NULL,
                  kind TEXT NOT NULL,
                  position INTEGER NOT NULL DEFAULT 0,
                  PRIMARY KEY(show_id, track_id),
                  FOREIGN KEY(show_id) REFERENCES shows(show_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS clips (
                  show_id TEXT NOT NULL,
                  track_id TEXT NOT NULL,
                  clip_id TEXT NOT NULL,
                  label TEXT NOT NULL,
                  start_ms INTEGER NOT NULL CHECK(start_ms >= 0),
                  duration_ms INTEGER NOT NULL CHECK(duration_ms > 0),
                  kind TEXT NOT NULL,
                  position INTEGER NOT NULL DEFAULT 0,
                  offset_ms INTEGER NOT NULL DEFAULT 0,
                  PRIMARY KEY(show_id, track_id, clip_id),
                  FOREIGN KEY(show_id, track_id) REFERENCES tracks(show_id, track_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS layers (
                  show_id TEXT NOT NULL,
                  track_id TEXT NOT NULL,
                  clip_id TEXT NOT NULL,
                  layer_id TEXT NOT NULL,
                  label TEXT NOT NULL,
                  asset_id TEXT,
                  opacity REAL NOT NULL DEFAULT 1.0,
                  blend_mode TEXT NOT NULL DEFAULT 'normal',
                  transform_json TEXT,
                  position INTEGER NOT NULL DEFAULT 0,
                  PRIMARY KEY(show_id, track_id, clip_id, layer_id),
                  FOREIGN KEY(show_id, track_id, clip_id) REFERENCES clips(show_id, track_id, clip_id) ON DELETE CASCADE
                );
                """
            )
            columns_shows = {row["name"] for row in conn.execute("PRAGMA table_info(shows)").fetchall()}
            if "mapping_config_json" not in columns_shows:
                conn.execute("ALTER TABLE shows ADD COLUMN mapping_config_json TEXT")

            columns_clips = {row["name"] for row in conn.execute("PRAGMA table_info(clips)").fetchall()}
            if "offset_ms" not in columns_clips:
                conn.execute("ALTER TABLE clips ADD COLUMN offset_ms INTEGER NOT NULL DEFAULT 0")
            conn.commit()

    def _seed_demo_show(self) -> None:
        if self.list_shows():
            return
        self.upsert_show("demo-show", 60000)
        self.upsert_track("demo-show", "video-main", "Video Main", "video", 0)
        self.upsert_track("demo-show", "alpha-overlay", "Alpha Overlay", "alpha", 1)
        self.upsert_track("demo-show", "audio-main", "Audio Main", "audio", 2)

        self.upsert_clip("demo-show", "video-main", "v1", "Intro Wall", 0, 12000, "video", 0)
        self.upsert_clip("demo-show", "video-main", "v2", "City Motion", 12500, 18000, "video", 1)
        self.upsert_clip("demo-show", "video-main", "v3", "Final Burst", 32000, 22000, "video", 2)
        self.upsert_clip("demo-show", "alpha-overlay", "a1", "Mask Sweep", 7000, 9000, "alpha", 0)
        self.upsert_clip("demo-show", "alpha-overlay", "a2", "Logo Reveal", 35000, 10000, "alpha", 1)
        self.upsert_clip("demo-show", "audio-main", "au1", "Sound Bed", 0, 50000, "audio", 0)

    def _show_exists(self, conn: sqlite3.Connection, show_id: str) -> bool:
        return conn.execute("SELECT 1 FROM shows WHERE show_id = ?", (show_id,)).fetchone() is not None

    def _track_exists(self, conn: sqlite3.Connection, show_id: str, track_id: str) -> bool:
        return (
            conn.execute(
                "SELECT 1 FROM tracks WHERE show_id = ? AND track_id = ?",
                (show_id, track_id),
            ).fetchone()
            is not None
        )

    def _next_track_position(self, conn: sqlite3.Connection, show_id: str) -> int:
        row = conn.execute("SELECT COALESCE(MAX(position), -1) AS max_pos FROM tracks WHERE show_id = ?", (show_id,)).fetchone()
        return int(row["max_pos"]) + 1

    def _next_clip_position(self, conn: sqlite3.Connection, show_id: str, track_id: str) -> int:
        row = conn.execute(
            """
            SELECT COALESCE(MAX(position), -1) AS max_pos
            FROM clips
            WHERE show_id = ? AND track_id = ?
            """,
            (show_id, track_id),
        ).fetchone()
        return int(row["max_pos"]) + 1
