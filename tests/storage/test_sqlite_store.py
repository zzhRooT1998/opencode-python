from pathlib import Path

from opencode_py.core.schemas import AgentState
from opencode_py.storage.sqlite_store import SQLiteStore


def test_sqlite_store_roundtrip_session_event_artifact_and_checkpoint(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "state.db")

    session = store.upsert_session("session-1", title="Demo task")
    event = store.add_event("session-1", "message", {"role": "user", "content": "hello"})
    artifact = store.add_artifact(
        "session-1",
        kind="patch",
        path="README.md",
        metadata={"lines_changed": 3},
    )
    checkpoint = store.save_checkpoint(
        session_id="session-1",
        step=2,
        state=AgentState(session_id="session-1", user_goal="Fix the CLI"),
    )

    assert session.id == "session-1"
    assert store.get_session("session-1") is not None
    assert store.list_events("session-1")[0].payload["content"] == "hello"
    assert store.list_artifacts("session-1")[0].path == "README.md"
    assert store.load_latest_checkpoint("session-1") is not None
    assert event.type == "message"
    assert artifact.kind == "patch"
    assert checkpoint.step == 2

