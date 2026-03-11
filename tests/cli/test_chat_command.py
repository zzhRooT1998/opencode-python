from pathlib import Path

from typer.testing import CliRunner

from opencode_py.cli.main import AppServices, app
from opencode_py.core.graph.orchestrator import OrchestratorResult


class FakeOrchestrator:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def run(self, *, session_id: str, user_goal: str) -> OrchestratorResult:
        self.calls.append({"session_id": session_id, "user_goal": user_goal})
        return OrchestratorResult(
            session_id=session_id,
            final_output=f"handled: {user_goal}",
            final_state={"session_id": session_id, "final_output": f"handled: {user_goal}"},
        )


def test_chat_command_loads_config_and_runs_runtime(monkeypatch, tmp_path: Path) -> None:
    fake_orchestrator = FakeOrchestrator()
    captured = {}

    def fake_create_app_services(*, settings, workspace_root, console):  # noqa: ANN001
        captured["model"] = settings.provider.model
        captured["workspace_root"] = workspace_root
        return AppServices(orchestrator=fake_orchestrator, repository=None)  # type: ignore[arg-type]

    monkeypatch.setattr("opencode_py.cli.main.create_app_services", fake_create_app_services)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "chat",
            "inspect the repository",
            "--model",
            "gpt-test",
            "--data-dir",
            str(tmp_path),
            "--workspace-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "handled: inspect the repository" in result.stdout
    assert captured["model"] == "gpt-test"
    assert captured["workspace_root"] == tmp_path

