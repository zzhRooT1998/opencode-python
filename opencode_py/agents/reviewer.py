"""Reviewer agent that accepts, revises, or aborts step results."""

from __future__ import annotations

import json
from typing import Any

from opencode_py.core.schemas import Message, ReviewDecision, ToolResult
from opencode_py.providers.base import Provider


class ReviewerAgent:
    """Review one step result against the original goal and constraints."""

    def __init__(self, provider: Provider) -> None:
        self.provider = provider

    def review(
        self,
        *,
        user_goal: str,
        step_title: str,
        step_output: str,
        tool_results: list[ToolResult],
    ) -> ReviewDecision:
        """Return one of accept, revise, or abort."""

        prompt_messages = [
            Message(
                role="system",
                content=(
                    "You are a reviewer. Return JSON only with fields: "
                    "outcome, rationale, retry_guidance."
                ),
            ),
            Message(
                role="user",
                content=self._build_prompt(
                    user_goal=user_goal,
                    step_title=step_title,
                    step_output=step_output,
                    tool_results=tool_results,
                ),
            ),
        ]
        output = self.provider.generate(prompt_messages, tools=[])
        parsed = self._parse_review(output.content)
        if parsed is not None:
            return parsed
        return self._fallback_review(step_output, tool_results)

    def _build_prompt(
        self,
        *,
        user_goal: str,
        step_title: str,
        step_output: str,
        tool_results: list[ToolResult],
    ) -> str:
        summarized_results = "\n".join(
            f"- {result.tool_name}: {result.status} :: {result.stderr or result.stdout[:120]}"
            for result in tool_results
        ) or "- no tools used"
        return (
            f"User goal: {user_goal}\n"
            f"Step: {step_title}\n"
            f"Step output: {step_output}\n"
            f"Tool results:\n{summarized_results}\n"
        )

    @staticmethod
    def _parse_review(content: str) -> ReviewDecision | None:
        try:
            parsed: Any = json.loads(content)
        except json.JSONDecodeError:
            return None

        if not isinstance(parsed, dict):
            return None

        outcome = parsed.get("outcome")
        if outcome not in {"accept", "revise", "abort"}:
            return None

        return ReviewDecision(
            outcome=outcome,
            rationale=str(parsed.get("rationale", "")) or "No rationale provided.",
            retry_guidance=parsed.get("retry_guidance"),
        )

    @staticmethod
    def _fallback_review(step_output: str, tool_results: list[ToolResult]) -> ReviewDecision:
        if any(result.status == "error" for result in tool_results):
            return ReviewDecision(
                outcome="revise",
                rationale="At least one tool call failed.",
                retry_guidance="Inspect the failed tool output and retry with a narrower action.",
            )
        if not step_output.strip():
            return ReviewDecision(
                outcome="revise",
                rationale="The step produced no output.",
                retry_guidance="Produce a concrete result for the current step.",
            )
        if "dangerous" in step_output.lower() or "abort" in step_output.lower():
            return ReviewDecision(
                outcome="abort",
                rationale="The result indicates unsafe execution.",
            )
        return ReviewDecision(
            outcome="accept",
            rationale="The step produced a usable result.",
        )

