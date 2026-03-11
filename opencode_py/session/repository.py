"""Repository helpers for session lifecycle operations."""

from __future__ import annotations

from opencode_py.core.schemas import AgentState, Message
from opencode_py.session.models import ArtifactRecord, CheckpointRecord, EventRecord, SessionHistory, SessionRecord
from opencode_py.storage.sqlite_store import SQLiteStore


class SessionRepository:
    """High-level session operations built on top of the SQLite store."""

    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    def start_session(self, session_id: str, title: str | None = None) -> SessionRecord:
        """Create or update session metadata."""

        return self._store.upsert_session(session_id=session_id, title=title)

    def list_sessions(self, limit: int = 50) -> list[SessionRecord]:
        """List the most recently updated sessions."""

        return self._store.list_sessions(limit=limit)

    def append_message(self, session_id: str, message: Message) -> EventRecord:
        """Persist one normalized message as an event."""

        return self._store.add_event(
            session_id=session_id,
            event_type="message",
            payload=message.model_dump(mode="json"),
        )

    def record_event(
        self,
        session_id: str,
        event_type: str,
        payload: dict[str, object] | None = None,
    ) -> EventRecord:
        """Persist an arbitrary runtime event."""

        return self._store.add_event(
            session_id=session_id,
            event_type=event_type,
            payload=payload or {},
        )

    def record_artifact(
        self,
        session_id: str,
        kind: str,
        path: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ArtifactRecord:
        """Persist an artifact emitted by a task."""

        return self._store.add_artifact(
            session_id=session_id,
            kind=kind,
            path=path,
            metadata=metadata or {},
        )

    def save_checkpoint(self, state: AgentState) -> CheckpointRecord:
        """Persist the latest graph state for resume support."""

        return self._store.save_checkpoint(
            session_id=state.session_id,
            step=state.current_step,
            state=state,
        )

    def load_session(self, session_id: str) -> SessionHistory | None:
        """Load stored session history and the latest checkpoint."""

        session = self._store.get_session(session_id)
        if session is None:
            return None

        events = self._store.list_events(session_id)
        messages = [
            Message.model_validate(event.payload)
            for event in events
            if event.type == "message"
        ]

        return SessionHistory(
            session=session,
            events=events,
            messages=messages,
            artifacts=self._store.list_artifacts(session_id),
            latest_checkpoint=self._store.load_latest_checkpoint(session_id),
        )
