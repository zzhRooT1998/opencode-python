from types import SimpleNamespace

from opencode_py.core.schemas import Message, ToolCall, ToolResult
from opencode_py.providers.base import ToolDefinition
from opencode_py.providers.openai_provider import OpenAIProvider


def test_provider_builds_request_payload() -> None:
    provider = OpenAIProvider(model="gpt-4o-mini", api_key="x", client=_fake_client())

    payload = provider._build_payload(
        messages=[
            Message(role="user", content="Inspect the repo"),
            Message(
                role="tool",
                content="",
                tool_result=ToolResult(
                    call_id="call-1",
                    tool_name="search",
                    status="success",
                    stdout="README.md",
                ),
            ),
            Message(
                role="assistant",
                content="Calling a tool",
                tool_calls=[ToolCall(name="search", arguments={"query": "README"}, call_id="call-1")],
            ),
        ],
        tools=[
            ToolDefinition(
                name="search",
                description="Search repository files",
                input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            )
        ],
    )

    assert payload["model"] == "gpt-4o-mini"
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][1]["role"] == "tool"
    assert payload["messages"][1]["tool_call_id"] == "call-1"
    assert payload["messages"][2]["tool_calls"][0]["function"]["name"] == "search"
    assert payload["tools"][0]["function"]["name"] == "search"


def test_provider_parses_text_and_tool_calls() -> None:
    provider = OpenAIProvider(model="gpt-4o-mini", api_key="x", client=_fake_client())

    response = SimpleNamespace(
        id="resp_123",
        choices=[
            SimpleNamespace(
                finish_reason="tool_calls",
                message=SimpleNamespace(
                    content="I should inspect the files first.",
                    tool_calls=[
                        SimpleNamespace(
                            id="call_1",
                            function=SimpleNamespace(
                                name="search",
                                arguments='{"query": "runtime"}',
                            ),
                        )
                    ],
                ),
            )
        ],
    )

    output = provider._parse_response(response)

    assert output.response_id == "resp_123"
    assert output.finish_reason == "tool_calls"
    assert output.content == "I should inspect the files first."
    assert output.tool_calls[0].name == "search"
    assert output.tool_calls[0].arguments["query"] == "runtime"


def test_provider_generate_uses_client_defaults() -> None:
    response = SimpleNamespace(
        id="resp_456",
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content="done", tool_calls=[]),
            )
        ],
    )
    client = _fake_client(response=response)
    provider = OpenAIProvider(
        model="gpt-4o-mini",
        api_key="x",
        client=client,
        timeout_seconds=30.0,
        max_retries=4,
    )

    output = provider.generate([Message(role="user", content="hello")])

    assert output.content == "done"
    assert provider.timeout_seconds == 30.0
    assert provider.max_retries == 4
    assert client.chat.completions.calls[0]["model"] == "gpt-4o-mini"


def _fake_client(response: object | None = None) -> SimpleNamespace:
    default_response = response or SimpleNamespace(
        id="resp_default",
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content="ok", tool_calls=[]),
            )
        ],
    )

    class FakeCompletions:
        def __init__(self, output: object) -> None:
            self._output = output
            self.calls: list[dict[str, object]] = []

        def create(self, **payload: object) -> object:
            self.calls.append(payload)
            return self._output

    completions = FakeCompletions(default_response)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))

