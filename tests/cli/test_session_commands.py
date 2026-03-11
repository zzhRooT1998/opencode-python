from pathlib import Path

from typer.testing import CliRunner

from opencode_py.cli.main import AppServices, app
from opencode_py.core.graph.orchestrator import OrchestratorResult
from opencode_py.core.schemas import AgentState, Message
from opencode_py.session.repository import SessionRepository
from opencode_py.storage.sqlite_store import SQLiteStore


class FakeResumeOrchestrator:
    def __init__(self) -> None:
        self.resumed_session_ids: list[str] = []

    def resume(self, session_id: str) -> OrchestratorResult:
        self.resumed_session_ids.append(session_id)
        return OrchestratorResult(
            session_id=session_id,
            final_output=f"resumed: {session_id}",
            final_state={"session_id": session_id, "final_output": f"resumed: {session_id}"},
        )


def test_session_list_and_show_render_saved_history(tmp_path: Path) -> None:
    repository = SessionRepository(SQLiteStore(tmp_path / "state.db"))
    repository.start_session("session-1", title="Inspect repository")
    repository.append_message("session-1", Message(role="user", content="inspect repository"))
    repository.record_event("session-1", "step_reviewed", {"decision": "continue"})
    repository.record_artifact(
        "session-1",
        kind="file",
        path="README.md",
        metadata={"step_id": "step-1"},
    )
    repository.save_checkpoint(
        AgentState(
            session_id="session-1",
            user_goal="inspect repository",
            messages=[Message(role="user", content="inspect repository")],
            current_step=1,
        )
    )

    runner = CliRunner()

    list_result = runner.invoke(
        app,
        ["session", "list", "--data-dir", str(tmp_path)],
    )
    show_result = runner.invoke(
        app,
        ["session", "show", "session-1", "--data-dir", str(tmp_path)],
    )

    assert list_result.exit_code == 0
    assert "session-1" in list_result.stdout
    assert "Inspect repository" in list_result.stdout

    assert show_result.exit_code == 0
    assert "Session Summary" in show_result.stdout
    assert "step_reviewed" in show_result.stdout
    assert "README.md" in show_result.stdout


def test_session_resume_uses_orchestrator_resume(monkeypatch, tmp_path: Path) -> None:
    fake_orchestrator = FakeResumeOrchestrator()

    def fake_create_app_services(*, settings, workspace_root, console):  # noqa: ANN001
        repository = SessionRepository(SQLiteStore(tmp_path / "state.db"))
        return AppServices(orchestrator=fake_orchestrator, repository=repository)

    monkeypatch.setattr("opencode_py.cli.main.create_app_services", fake_create_app_services)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "session",
            "resume",
            "session-2",
            "--data-dir",
            str(tmp_path),
            "--workspace-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "resumed: session-2" in result.stdout
    assert fake_orchestrator.resumed_session_ids == ["session-2"]

