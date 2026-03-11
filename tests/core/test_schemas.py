from opencode_py.core.schemas import AgentState, Message, PlanStep, ToolCall, ToolResult


def test_tool_call_schema_roundtrip() -> None:
    call = ToolCall(name="shell", arguments={"cmd": "pwd"}, call_id="1")
    result = ToolResult(call_id="1", tool_name="shell", status="success", stdout="ok")
    message = Message(role="assistant", content="", tool_calls=[call], tool_result=result)

    assert message.tool_calls[0].name == "shell"
    assert message.tool_result is not None
    assert message.tool_result.stdout == "ok"


def test_agent_state_uses_safe_collection_defaults() -> None:
    state = AgentState(
        session_id="session-1",
        user_goal="Fix the failing CLI smoke test",
        plan_steps=[
            PlanStep(
                id="step-1",
                title="Inspect CLI entry point",
                objective="Read CLI code",
                success_criteria="Identify command group shape",
            )
        ],
    )

    assert state.messages == []
    assert state.retrieval_hits == []
    assert state.artifacts == {}
    assert state.plan_steps[0].title == "Inspect CLI entry point"

