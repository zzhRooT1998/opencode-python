"""Planner agent that turns a task goal into structured steps."""

from __future__ import annotations

import json
from typing import Any

from opencode_py.core.schemas import Message, PlanStep
from opencode_py.providers.base import Provider
from opencode_py.retrieval.service import RetrievalHit


class PlannerAgent:
    """Generate a bounded step plan from the user goal and retrieved evidence."""

    def __init__(self, provider: Provider, max_steps: int = 8) -> None:
        self.provider = provider
        self.max_steps = max_steps

    def plan(
        self,
        *,
        user_goal: str,
        retrieval_hits: list[RetrievalHit],
        message_history: list[Message] | None = None,
    ) -> list[PlanStep]:
        """Return structured plan steps for the current task."""

        history = message_history or []
        prompt_messages = [
            Message(
                role="system",
                content=(
                    "You are a planning agent. Produce JSON only with a top-level `steps` "
                    "array. Each step needs: id, title, objective, suggested_tools, success_criteria."
                ),
            ),
            *history[-4:],
            Message(
                role="user",
                content=self._build_prompt(user_goal=user_goal, retrieval_hits=retrieval_hits),
            ),
        ]
        output = self.provider.generate(prompt_messages, tools=[])
        return self._parse_plan(output.content, user_goal)

    def _build_prompt(self, *, user_goal: str, retrieval_hits: list[RetrievalHit]) -> str:
        evidence = "\n".join(
            f"- {hit.path}:{hit.line_start}-{hit.line_end} ({hit.reason})"
            for hit in retrieval_hits[:5]
        ) or "- no evidence available"
        return (
            f"User goal:\n{user_goal}\n\n"
            f"Relevant evidence:\n{evidence}\n\n"
            f"Limit the plan to at most {self.max_steps} steps."
        )

    def _parse_plan(self, content: str, user_goal: str) -> list[PlanStep]:
        parsed = _safe_json_load(content)
        if isinstance(parsed, dict):
            raw_steps = parsed.get("steps", [])
            steps = [_plan_step_from_raw(step, index) for index, step in enumerate(raw_steps, start=1)]
            steps = [step for step in steps if step is not None][: self.max_steps]
            if steps:
                return steps

        return [
            PlanStep(
                id="step-1",
                title="Complete requested task",
                objective=user_goal,
                suggested_tools=["search", "fs_read", "shell"],
                success_criteria="Return a result that addresses the user goal.",
            )
        ]


def _safe_json_load(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def _plan_step_from_raw(raw: Any, index: int) -> PlanStep | None:
    if not isinstance(raw, dict):
        return None
    objective = str(raw.get("objective", "")).strip()
    if not objective:
        return None
    return PlanStep(
        id=str(raw.get("id") or f"step-{index}"),
        title=str(raw.get("title") or objective[:50]),
        objective=objective,
        suggested_tools=[str(tool) for tool in raw.get("suggested_tools", [])],
        success_criteria=str(raw.get("success_criteria") or "Step completed successfully."),
    )

