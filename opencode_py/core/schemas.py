"""Shared schemas for messages, tools, and graph state."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


MessageRole = Literal["system", "user", "assistant", "tool"]
Decision = Literal["continue", "retry", "done", "abort"]
ReviewOutcome = Literal["accept", "revise", "abort"]


class ToolCall(BaseModel):
    """A tool invocation requested by the model."""

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    call_id: str


class ToolResult(BaseModel):
    """Normalized result returned by a tool runtime."""

    call_id: str
    tool_name: str
    status: Literal["success", "error"]
    stdout: str = ""
    stderr: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)


class Message(BaseModel):
    """Normalized chat message shared across providers and runtime."""

    role: MessageRole
    content: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_result: ToolResult | None = None


class PlanStep(BaseModel):
    """Planner output for one executable step."""

    id: str
    title: str
    objective: str
    suggested_tools: list[str] = Field(default_factory=list)
    success_criteria: str


class ReviewDecision(BaseModel):
    """Reviewer output for a completed step."""

    outcome: ReviewOutcome
    rationale: str
    retry_guidance: str | None = None


class AgentState(BaseModel):
    """Shared graph state between nodes."""

    session_id: str
    user_goal: str
    messages: list[Message] = Field(default_factory=list)
    plan_steps: list[PlanStep] = Field(default_factory=list)
    current_step: int = 0
    retrieval_hits: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    review_notes: str | None = None
    decision: Decision = "continue"
    trace_id: str | None = None

