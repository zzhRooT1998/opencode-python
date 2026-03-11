"""Session-level models backed by persistent storage."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from opencode_py.core.schemas import AgentState, Message


class SessionRecord(BaseModel):
    """Stored session metadata."""

    id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class EventRecord(BaseModel):
    """Stored session event."""

    id: int
    session_id: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ArtifactRecord(BaseModel):
    """Stored task artifact."""

    id: int
    session_id: str
    kind: str
    path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class CheckpointRecord(BaseModel):
    """Stored graph checkpoint."""

    id: int
    session_id: str
    step: int
    state: AgentState
    created_at: datetime


class SessionHistory(BaseModel):
    """Aggregated view used by runtime and CLI."""

    session: SessionRecord
    events: list[EventRecord] = Field(default_factory=list)
    messages: list[Message] = Field(default_factory=list)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    latest_checkpoint: CheckpointRecord | None = None

