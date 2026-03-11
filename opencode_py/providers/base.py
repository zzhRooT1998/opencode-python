"""Provider abstractions for model backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from opencode_py.core.schemas import Message, ToolCall


class ToolDefinition(BaseModel):
    """Tool specification exposed to the model."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)


class ProviderOutput(BaseModel):
    """Normalized model output."""

    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str | None = None
    response_id: str | None = None


class Provider(ABC):
    """Abstract provider interface used by the runtime."""

    @abstractmethod
    def generate(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> ProviderOutput:
        """Generate one assistant turn from normalized messages."""

