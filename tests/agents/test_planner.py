from opencode_py.agents.planner import PlannerAgent
from opencode_py.core.schemas import Message
from opencode_py.providers.base import Provider, ProviderOutput
from opencode_py.retrieval.service import RetrievalHit


class FakeProvider(Provider):
    def __init__(self, content: str) -> None:
        self.content = content

    def generate(self, messages: list[Message], tools=None) -> ProviderOutput:  # type: ignore[override]
        return ProviderOutput(content=self.content)


def test_planner_returns_structured_steps_from_json() -> None:
    provider = FakeProvider(
        """
        {
          "steps": [
            {
              "id": "step-1",
              "title": "Inspect CLI",
              "objective": "Read the CLI entrypoint",
              "suggested_tools": ["fs_read", "search"],
              "success_criteria": "Understand how commands are wired"
            }
          ]
        }
        """
    )
    planner = PlannerAgent(provider)

    steps = planner.plan(
        user_goal="Understand the CLI",
        retrieval_hits=[
            RetrievalHit(
                path="opencode_py/cli/main.py",
                line_start=1,
                line_end=10,
                snippet="app = typer.Typer()",
                score=5.0,
                reason="Matched CLI terms.",
            )
        ],
    )

    assert steps[0].id == "step-1"
    assert steps[0].suggested_tools == ["fs_read", "search"]


def test_planner_falls_back_to_single_step_when_output_is_not_json() -> None:
    planner = PlannerAgent(FakeProvider("not-json-response"))

    steps = planner.plan(user_goal="Fix failing tests", retrieval_hits=[])

    assert len(steps) == 1
    assert steps[0].objective == "Fix failing tests"

