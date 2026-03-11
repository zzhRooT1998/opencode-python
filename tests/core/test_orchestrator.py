from pathlib import Path

from opencode_py.agents.executor import ExecutorAgent
from opencode_py.agents.planner import PlannerAgent
from opencode_py.agents.reviewer import ReviewerAgent
from opencode_py.core.graph.orchestrator import LangGraphOrchestrator
from opencode_py.core.schemas import Message
from opencode_py.providers.base import Provider, ProviderOutput
from opencode_py.retrieval.service import RetrievalService
from opencode_py.security.policy import PermissionPolicy
from opencode_py.session.repository import SessionRepository
from opencode_py.storage.sqlite_store import SQLiteStore
from opencode_py.tools import ToolRuntime


class SequencedProvider(Provider):
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)

    def generate(self, messages: list[Message], tools=None) -> ProviderOutput:  # type: ignore[override]
        return ProviderOutput(content=self.outputs.pop(0))


def test_orchestrator_runs_single_step_flow_and_saves_checkpoint(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def run_cli():\n    return 'ok'\n", encoding="utf-8")
    repository = SessionRepository(SQLiteStore(tmp_path / "state.db"))
    orchestrator = LangGraphOrchestrator(
        repository=repository,
        retrieval_service=RetrievalService(tmp_path),
        planner=PlannerAgent(
            SequencedProvider(
                [
                    '{"steps": [{"id": "step-1", "title": "Inspect", "objective": "Read app.py", "suggested_tools": [], "success_criteria": "Know the structure"}]}'
                ]
            )
        ),
        executor=ExecutorAgent(
            provider=SequencedProvider(["Inspected the file."]),
            runtime=ToolRuntime(
                tools=[],
                policy=PermissionPolicy(mode="allow", workspace_root=tmp_path),
                workspace_root=tmp_path,
            ),
        ),
        reviewer=ReviewerAgent(
            SequencedProvider(['{"outcome": "accept", "rationale": "Looks good.", "retry_guidance": null}'])
        ),
    )

    result = orchestrator.run(session_id="session-1", user_goal="Inspect the app")
    history = repository.load_session("session-1")

    assert result.final_output == "Inspected the file."
    assert history is not None
    assert history.latest_checkpoint is not None
    assert history.latest_checkpoint.state.current_step == 0


def test_orchestrator_retries_when_reviewer_requests_revision(tmp_path: Path) -> None:
    repository = SessionRepository(SQLiteStore(tmp_path / "state.db"))
    orchestrator = LangGraphOrchestrator(
        repository=repository,
        retrieval_service=RetrievalService(tmp_path),
        planner=PlannerAgent(
            SequencedProvider(
                [
                    '{"steps": [{"id": "step-1", "title": "Inspect", "objective": "Read app.py", "suggested_tools": [], "success_criteria": "Know the structure"}]}'
                ]
            )
        ),
        executor=ExecutorAgent(
            provider=SequencedProvider(["First try", "Second try"]),
            runtime=ToolRuntime(
                tools=[],
                policy=PermissionPolicy(mode="allow", workspace_root=tmp_path),
                workspace_root=tmp_path,
            ),
        ),
        reviewer=ReviewerAgent(
            SequencedProvider(
                [
                    '{"outcome": "revise", "rationale": "Need more detail.", "retry_guidance": "Try again."}',
                    '{"outcome": "accept", "rationale": "Good now.", "retry_guidance": null}',
                ]
            )
        ),
        max_retries=2,
    )

    result = orchestrator.run(session_id="session-2", user_goal="Inspect the app")

    assert result.final_output == "Second try"
    assert result.final_state["retries"] == 0

