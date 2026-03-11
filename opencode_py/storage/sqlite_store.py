"""SQLite-backed storage for sessions, events, artifacts, and checkpoints."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from opencode_py.core.schemas import AgentState
from opencode_py.session.models import ArtifactRecord, CheckpointRecord, EventRecord, SessionRecord


class SQLiteStore:
    """Simple SQLite storage wrapper for single-user local execution."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @property
    def db_path(self) -> Path:
        """Return the resolved database path."""

        return self._db_path

    @contextmanager
    def connection(self) -> sqlite3.Connection:
        """Create a connection with row access by column name."""

        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        """Create all required tables if they do not already exist."""

        with self.connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    path TEXT,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    step INTEGER NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );
                """
            )

    def upsert_session(self, session_id: str, title: str | None = None) -> SessionRecord:
        """Create or update a session record."""

        timestamp = _utcnow().isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = COALESCE(excluded.title, sessions.title),
                    updated_at = excluded.updated_at
                """,
                (session_id, title, timestamp, timestamp),
            )
            row = conn.execute(
                "SELECT id, title, created_at, updated_at FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        return _session_from_row(row)

    def get_session(self, session_id: str) -> SessionRecord | None:
        """Load one session by id."""

        with self.connection() as conn:
            row = conn.execute(
                "SELECT id, title, created_at, updated_at FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return _session_from_row(row)

    def list_sessions(self, limit: int = 50) -> list[SessionRecord]:
        """List the most recently updated sessions."""

        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM sessions
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_session_from_row(row) for row in rows]

    def add_event(
        self,
        session_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> EventRecord:
        """Persist one runtime event."""

        self.upsert_session(session_id=session_id)
        timestamp = _utcnow().isoformat()
        payload_json = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)

        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO events (session_id, type, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, event_type, payload_json, timestamp),
            )
            self._touch_session(conn, session_id, timestamp)
            row = conn.execute(
                """
                SELECT id, session_id, type, payload_json, created_at
                FROM events
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        return _event_from_row(row)

    def list_events(self, session_id: str) -> list[EventRecord]:
        """List all events for one session in insertion order."""

        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, type, payload_json, created_at
                FROM events
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
        return [_event_from_row(row) for row in rows]

    def add_artifact(
        self,
        session_id: str,
        kind: str,
        path: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactRecord:
        """Persist a task artifact."""

        self.upsert_session(session_id=session_id)
        timestamp = _utcnow().isoformat()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)

        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO artifacts (session_id, kind, path, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, kind, path, metadata_json, timestamp),
            )
            self._touch_session(conn, session_id, timestamp)
            row = conn.execute(
                """
                SELECT id, session_id, kind, path, metadata_json, created_at
                FROM artifacts
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        return _artifact_from_row(row)

    def list_artifacts(self, session_id: str) -> list[ArtifactRecord]:
        """List persisted artifacts for one session."""

        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, kind, path, metadata_json, created_at
                FROM artifacts
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
        return [_artifact_from_row(row) for row in rows]

    def save_checkpoint(self, session_id: str, step: int, state: AgentState) -> CheckpointRecord:
        """Persist one checkpoint snapshot."""

        self.upsert_session(session_id=session_id)
        timestamp = _utcnow().isoformat()
        state_json = state.model_dump_json()

        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO checkpoints (session_id, step, state_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, step, state_json, timestamp),
            )
            self._touch_session(conn, session_id, timestamp)
            row = conn.execute(
                """
                SELECT id, session_id, step, state_json, created_at
                FROM checkpoints
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        return _checkpoint_from_row(row)

    def load_latest_checkpoint(self, session_id: str) -> CheckpointRecord | None:
        """Load the most recent checkpoint for one session."""

        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT id, session_id, step, state_json, created_at
                FROM checkpoints
                WHERE session_id = ?
                ORDER BY step DESC, id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return _checkpoint_from_row(row)

    @staticmethod
    def _touch_session(conn: sqlite3.Connection, session_id: str, timestamp: str) -> None:
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (timestamp, session_id),
        )


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _session_from_row(row: sqlite3.Row) -> SessionRecord:
    return SessionRecord(
        id=row["id"],
        title=row["title"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _event_from_row(row: sqlite3.Row) -> EventRecord:
    return EventRecord(
        id=row["id"],
        session_id=row["session_id"],
        type=row["type"],
        payload=json.loads(row["payload_json"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _artifact_from_row(row: sqlite3.Row) -> ArtifactRecord:
    return ArtifactRecord(
        id=row["id"],
        session_id=row["session_id"],
        kind=row["kind"],
        path=row["path"],
        metadata=json.loads(row["metadata_json"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _checkpoint_from_row(row: sqlite3.Row) -> CheckpointRecord:
    return CheckpointRecord(
        id=row["id"],
        session_id=row["session_id"],
        step=row["step"],
        state=AgentState.model_validate_json(row["state_json"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )

