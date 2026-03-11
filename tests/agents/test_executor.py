from opencode_py.agents.executor import ExecutorAgent
from opencode_py.core.schemas import Message, PlanStep, ToolCall
from opencode_py.providers.base import Provider, ProviderOutput
from opencode_py.security.policy import PermissionPolicy
from opencode_py.tools import FSReadTool, ToolRuntime


class FakeExecutorProvider(Provider):
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, messages: list[Message], tools=None) -> ProviderOutput:  # type: ignore[override]
        self.calls += 1
        if self.calls == 1:
            return ProviderOutput(
                content="I need to inspect the file.",
                tool_calls=[ToolCall(name="fs_read", arguments={"path": "README.md"}, call_id="call-1")],
            )
        assert messages[-1].role == "tool"
        return ProviderOutput(content="The file was inspected successfully.")


class DirectAnswerProvider(Provider):
    def generate(self, messages: list[Message], tools=None) -> ProviderOutput:  # type: ignore[override]
        return ProviderOutput(content="Done without tools.")


def test_executor_runs_react_loop_with_tool_results(tmp_path) -> None:
    (tmp_path / "README.md").write_text("hello world", encoding="utf-8")
    runtime = ToolRuntime(
        tools=[FSReadTool()],
        policy=PermissionPolicy(mode="allow", workspace_root=tmp_path),
        workspace_root=tmp_path,
    )
    executor = ExecutorAgent(provider=FakeExecutorProvider(), runtime=runtime)

    result = executor.execute(
        step=PlanStep(
            id="step-1",
            title="Inspect file",
            objective="Read the README",
            suggested_tools=["fs_read"],
            success_criteria="Know the file contents",
        ),
        retrieval_hits=[],
    )

    assert result.final_output == "The file was inspected successfully."
    assert len(result.tool_results) == 1
    assert result.tool_results[0].status == "success"
    assert any(message.role == "tool" for message in result.messages)


def test_executor_supports_direct_answer_without_tools(tmp_path) -> None:
    runtime = ToolRuntime(
        tools=[FSReadTool()],
        policy=PermissionPolicy(mode="allow", workspace_root=tmp_path),
        workspace_root=tmp_path,
    )
    executor = ExecutorAgent(provider=DirectAnswerProvider(), runtime=runtime)

    result = executor.execute(
        step=PlanStep(
            id="step-1",
            title="Summarize step",
            objective="Return the answer",
            suggested_tools=[],
            success_criteria="Provide the answer",
        ),
        retrieval_hits=[],
    )

    assert result.final_output == "Done without tools."
    assert result.tool_results == []
    assert result.stopped_due_to_max_iterations is False

