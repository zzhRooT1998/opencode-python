from pathlib import Path

from typer.testing import CliRunner

from opencode_py.agents import ExecutorAgent, PlannerAgent, ReviewerAgent
from opencode_py.cli.main import AppServices, app
from opencode_py.core.graph import LangGraphOrchestrator
from opencode_py.core.schemas import Message
from opencode_py.providers.base import Provider, ProviderOutput
from opencode_py.retrieval import RetrievalService
from opencode_py.security.policy import PermissionPolicy
from opencode_py.session.repository import SessionRepository
from opencode_py.storage import SQLiteStore
from opencode_py.tools import ToolRuntime


class SequencedProvider(Provider):
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)

    def generate(self, messages: list[Message], tools=None) -> ProviderOutput:  # type: ignore[override]
        return ProviderOutput(content=self.outputs.pop(0))


def test_run_command_executes_end_to_end_with_real_orchestrator(monkeypatch, tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "app.py").write_text(
        "def greet(name: str) -> str:\n    return f'Hello, {name}'\n",
        encoding="utf-8",
    )
    data_dir = tmp_path / "data"

    repository = SessionRepository(SQLiteStore(data_dir / "state.db"))
    orchestrator = LangGraphOrchestrator(
        repository=repository,
        retrieval_service=RetrievalService(workspace_root),
        planner=PlannerAgent(
            SequencedProvider(
                [
                    '{"steps": [{"id": "step-1", "title": "Inspect", "objective": "Inspect greet implementation", "suggested_tools": [], "success_criteria": "Summarize the function"}]}'
                ]
            )
        ),
        executor=ExecutorAgent(
            provider=SequencedProvider(["The greet function returns a formatted hello string."]),
            runtime=ToolRuntime(
                tools=[],
                policy=PermissionPolicy(mode="allow", workspace_root=workspace_root),
                workspace_root=workspace_root,
            ),
        ),
        reviewer=ReviewerAgent(
            SequencedProvider(['{"outcome": "accept", "rationale": "Answer is sufficient.", "retry_guidance": null}'])
        ),
    )

    def fake_create_app_services(*, settings, workspace_root, console):  # noqa: ANN001
        return AppServices(orchestrator=orchestrator, repository=repository)

    monkeypatch.setattr("opencode_py.cli.main.create_app_services", fake_create_app_services)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "inspect the greeting flow",
            "--session-id",
            "e2e-session",
            "--data-dir",
            str(data_dir),
            "--workspace-root",
            str(workspace_root),
        ],
    )

    history = repository.load_session("e2e-session")

    assert result.exit_code == 0
    assert "The greet function returns a formatted hello string." in result.stdout
    assert history is not None
    assert history.latest_checkpoint is not None
    assert history.messages[-1].content == "The greet function returns a formatted hello string."
