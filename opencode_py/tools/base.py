"""Base tool protocol and shared context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from opencode_py.core.schemas import ToolResult


@dataclass(slots=True)
class ToolContext:
    """Execution context shared by tool invocations."""

    workspace_root: Path
    env: dict[str, str] = field(default_factory=dict)


class Tool(ABC):
    """Base interface implemented by all tools."""

    name: str
    description: str

    @abstractmethod
    def invoke(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        """Execute the tool and return a normalized result."""

