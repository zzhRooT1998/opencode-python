"""Executor agent with a ReAct-style tool loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from opencode_py.core.schemas import Message, PlanStep, ToolCall, ToolResult
from opencode_py.providers.base import Provider, ToolDefinition
from opencode_py.retrieval.service import RetrievalHit
from opencode_py.security.policy import PermissionDecision
from opencode_py.tools.runtime import ToolRuntime


ApprovalHandler = Callable[[ToolCall, PermissionDecision], bool]


@dataclass(slots=True)
class ExecutorResult:
    """Execution output for one step."""

    final_output: str
    messages: list[Message] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    stopped_due_to_max_iterations: bool = False


class ExecutorAgent:
    """Run one plan step through a ReAct-style loop."""

    def __init__(
        self,
        provider: Provider,
        runtime: ToolRuntime,
        *,
        approval_handler: ApprovalHandler | None = None,
        max_iterations: int = 5,
    ) -> None:
        self.provider = provider
        self.runtime = runtime
        self.approval_handler = approval_handler
        self.max_iterations = max_iterations

    def execute(
        self,
        *,
        step: PlanStep,
        retrieval_hits: list[RetrievalHit],
        message_history: list[Message] | None = None,
    ) -> ExecutorResult:
        """Execute one step and return the resulting message trail."""

        conversation = list(message_history or [])
        conversation.extend(
            [
                Message(role="system", content=_system_prompt(step)),
                Message(role="user", content=_step_prompt(step, retrieval_hits)),
            ]
        )

        tool_definitions = [
            ToolDefinition(
                name=tool.name,
                description=getattr(tool, "description", ""),
                input_schema=getattr(tool, "input_schema", {"type": "object", "properties": {}}),
            )
            for tool in self.runtime.tools.values()
        ]

        tool_results: list[ToolResult] = []
        artifacts: list[str] = []
        final_output = ""

        for iteration in range(self.max_iterations):
            output = self.provider.generate(conversation, tools=tool_definitions)
            assistant_message = Message(
                role="assistant",
                content=output.content,
                tool_calls=output.tool_calls,
            )
            conversation.append(assistant_message)
            final_output = output.content

            if not output.tool_calls:
                return ExecutorResult(
                    final_output=final_output,
                    messages=conversation,
                    artifacts=artifacts,
                    tool_results=tool_results,
                )

            for tool_call in output.tool_calls:
                approved = self._is_approved(tool_call)
                result = self.runtime.invoke(
                    tool_call.name,
                    {**tool_call.arguments, "call_id": tool_call.call_id},
                    approved=approved,
                )
                tool_results.append(result)
                artifacts.extend(result.artifacts)
                conversation.append(Message(role="tool", content="", tool_result=result))

        return ExecutorResult(
            final_output=final_output,
            messages=conversation,
            artifacts=artifacts,
            tool_results=tool_results,
            stopped_due_to_max_iterations=True,
        )

    def _is_approved(self, tool_call: ToolCall) -> bool:
        if self.approval_handler is None:
            return False
        decision = self.runtime.policy.check(tool_call.name, tool_call.arguments)
        if not decision.requires_confirmation:
            return False
        return self.approval_handler(tool_call, decision)


def _system_prompt(step: PlanStep) -> str:
    return (
        "You are the execution agent. Use tools only when necessary. "
        "When you have enough evidence, produce a concise step result."
    )


def _step_prompt(step: PlanStep, retrieval_hits: list[RetrievalHit]) -> str:
    evidence = "\n".join(
        f"- {hit.path}:{hit.line_start}-{hit.line_end}\n{hit.snippet}"
        for hit in retrieval_hits[:5]
    ) or "- no retrieval evidence"
    return (
        f"Step title: {step.title}\n"
        f"Objective: {step.objective}\n"
        f"Success criteria: {step.success_criteria}\n"
        f"Suggested tools: {', '.join(step.suggested_tools) or 'none'}\n\n"
        f"Evidence:\n{evidence}"
    )

