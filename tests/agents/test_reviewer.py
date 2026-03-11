from opencode_py.agents.reviewer import ReviewerAgent
from opencode_py.core.schemas import Message, ToolResult
from opencode_py.providers.base import Provider, ProviderOutput


class FakeReviewerProvider(Provider):
    def __init__(self, content: str) -> None:
        self.content = content

    def generate(self, messages: list[Message], tools=None) -> ProviderOutput:  # type: ignore[override]
        return ProviderOutput(content=self.content)


def test_reviewer_parses_json_decision() -> None:
    reviewer = ReviewerAgent(
        FakeReviewerProvider(
            '{"outcome": "accept", "rationale": "Looks correct.", "retry_guidance": null}'
        )
    )

    decision = reviewer.review(
        user_goal="Fix the bug",
        step_title="Apply patch",
        step_output="Patch applied and tests pass.",
        tool_results=[],
    )

    assert decision.outcome == "accept"
    assert decision.rationale == "Looks correct."


def test_reviewer_falls_back_to_revise_on_tool_error() -> None:
    reviewer = ReviewerAgent(FakeReviewerProvider("not-json"))

    decision = reviewer.review(
        user_goal="Inspect files",
        step_title="Run search",
        step_output="",
        tool_results=[
            ToolResult(
                call_id="call-1",
                tool_name="search",
                status="error",
                stderr="timeout",
            )
        ],
    )

    assert decision.outcome == "revise"
    assert "failed" in decision.rationale.lower()

