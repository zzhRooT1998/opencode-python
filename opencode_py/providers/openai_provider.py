"""OpenAI-compatible provider implementation."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from opencode_py.core.schemas import Message, ToolCall
from opencode_py.providers.base import Provider, ProviderOutput, ToolDefinition


class OpenAIProvider(Provider):
    """Provider backed by an OpenAI-compatible chat completions API."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        client: OpenAI | Any | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._client = client or OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )

    def generate(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> ProviderOutput:
        """Generate one assistant turn from normalized messages."""

        payload = self._build_payload(messages, tools)
        response = self._client.chat.completions.create(**payload)
        return self._parse_response(response)

    def _build_payload(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [self._serialize_message(message) for message in messages],
        }
        if tools:
            payload["tools"] = [self._serialize_tool(tool) for tool in tools]
        return payload

    def _serialize_message(self, message: Message) -> dict[str, Any]:
        if message.role == "tool":
            if message.tool_result is None:
                raise ValueError("Tool messages require tool_result data.")
            return {
                "role": "tool",
                "tool_call_id": message.tool_result.call_id,
                "content": _tool_content(message),
            }

        payload: dict[str, Any] = {
            "role": message.role,
            "content": message.content,
        }
        if message.role == "assistant" and message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": call.call_id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                    },
                }
                for call in message.tool_calls
            ]
        return payload

    @staticmethod
    def _serialize_tool(tool: ToolDefinition) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            },
        }

    @staticmethod
    def _parse_response(response: Any) -> ProviderOutput:
        choice = response.choices[0]
        message = choice.message

        tool_calls = [
            ToolCall(
                name=tool_call.function.name,
                arguments=json.loads(tool_call.function.arguments or "{}"),
                call_id=tool_call.id,
            )
            for tool_call in (message.tool_calls or [])
        ]

        return ProviderOutput(
            content=_normalize_content(message.content),
            tool_calls=tool_calls,
            finish_reason=getattr(choice, "finish_reason", None),
            response_id=getattr(response, "id", None),
        )


def _normalize_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                    continue
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
                    continue
            elif hasattr(item, "text") and isinstance(item.text, str):
                parts.append(item.text)
        return "\n".join(part for part in parts if part)
    return str(content)


def _tool_content(message: Message) -> str:
    if message.content:
        return message.content
    if message.tool_result is None:
        return ""

    payload = {
        "status": message.tool_result.status,
        "stdout": message.tool_result.stdout,
        "stderr": message.tool_result.stderr,
        "metadata": message.tool_result.metadata,
    }
    return json.dumps(payload, ensure_ascii=False)

