from pathlib import Path

from opencode_py.core.schemas import AgentState, Message
from opencode_py.session.repository import SessionRepository
from opencode_py.storage.sqlite_store import SQLiteStore


def test_session_repository_restores_messages_and_latest_checkpoint(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "state.db")
    repository = SessionRepository(store)

    repository.start_session("session-1", title="Debug flow")
    repository.append_message("session-1", Message(role="user", content="Find the bug"))
    repository.append_message("session-1", Message(role="assistant", content="Inspecting files"))
    repository.record_artifact(
        "session-1",
        kind="report",
        path="logs/output.txt",
        metadata={"status": "generated"},
    )
    repository.save_checkpoint(
        AgentState(
            session_id="session-1",
            user_goal="Find the bug",
            current_step=1,
            messages=[Message(role="user", content="Find the bug")],
        )
    )

    history = repository.load_session("session-1")

    assert history is not None
    assert history.session.id == "session-1"
    assert [message.role for message in history.messages] == ["user", "assistant"]
    assert history.latest_checkpoint is not None
    assert history.latest_checkpoint.step == 1
    assert history.artifacts[0].kind == "report"

