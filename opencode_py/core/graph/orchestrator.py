"""LangGraph-based task orchestrator."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph

from opencode_py.agents.executor import ExecutorAgent
from opencode_py.agents.planner import PlannerAgent
from opencode_py.agents.reviewer import ReviewerAgent
from opencode_py.core.schemas import AgentState, Message, PlanStep, ToolResult
from opencode_py.retrieval.service import RetrievalHit, RetrievalService
from opencode_py.session.repository import SessionRepository


class GraphState(TypedDict, total=False):
    session_id: str
    user_goal: str
    messages: list[Message]
    plan_steps: list[PlanStep]
    current_step: int
    retrieval_hits: list[RetrievalHit]
    artifacts: dict[str, Any]
    review_notes: str | None
    decision: str
    trace_id: str
    retries: int
    current_output: str
    current_tool_results: list[ToolResult]
    final_output: str


@dataclass(slots=True)
class OrchestratorResult:
    """Final orchestrator output."""

    session_id: str
    final_output: str
    final_state: GraphState


class LangGraphOrchestrator:
    """Coordinate retrieval, planning, execution, and review through LangGraph."""

    def __init__(
        self,
        *,
        repository: SessionRepository,
        retrieval_service: RetrievalService,
        planner: PlannerAgent,
        executor: ExecutorAgent,
        reviewer: ReviewerAgent,
        max_retries: int = 2,
    ) -> None:
        self.repository = repository
        self.retrieval_service = retrieval_service
        self.planner = planner
        self.executor = executor
        self.reviewer = reviewer
        self.max_retries = max_retries
        self.graph = self._build_graph()

    def run(
        self,
        *,
        session_id: str,
        user_goal: str,
        message_history: list[Message] | None = None,
    ) -> OrchestratorResult:
        """Run a fresh task from the initial state."""

        self.repository.start_session(session_id, title=user_goal[:80])
        initial_messages = list(message_history or [])
        if not initial_messages:
            initial_messages.append(Message(role="user", content=user_goal))
            self.repository.append_message(session_id, initial_messages[0])

        initial_state: GraphState = {
            "session_id": session_id,
            "user_goal": user_goal,
            "messages": initial_messages,
            "plan_steps": [],
            "current_step": 0,
            "retrieval_hits": [],
            "artifacts": {},
            "review_notes": None,
            "decision": "continue",
            "trace_id": str(uuid4()),
            "retries": 0,
            "current_output": "",
            "current_tool_results": [],
            "final_output": "",
        }
        final_state = self.graph.invoke(initial_state)
        return self._finalize_result(final_state)

    def resume(self, session_id: str) -> OrchestratorResult:
        """Resume execution from the latest persisted checkpoint."""

        history = self.repository.load_session(session_id)
        if history is None or history.latest_checkpoint is None:
            raise ValueError(f"No checkpoint found for session {session_id}.")

        checkpoint_state = _agent_state_to_graph_state(history.latest_checkpoint.state)
        final_state = self.graph.invoke(checkpoint_state)
        return self._finalize_result(final_state)

    def _build_graph(self):
        graph = StateGraph(GraphState)
        graph.add_node("load_context", self._load_context)
        graph.add_node("retrieve_context", self._retrieve_context)
        graph.add_node("plan", self._plan)
        graph.add_node("execute_step", self._execute_step)
        graph.add_node("review_step", self._review_step)
        graph.add_node("commit_or_retry", self._commit_or_retry)
        graph.add_node("finalize", self._finalize)

        graph.set_entry_point("load_context")
        graph.add_edge("load_context", "retrieve_context")
        graph.add_conditional_edges(
            "retrieve_context",
            self._route_after_retrieve,
            {"plan": "plan", "execute_step": "execute_step"},
        )
        graph.add_edge("plan", "retrieve_context")
        graph.add_edge("execute_step", "review_step")
        graph.add_edge("review_step", "commit_or_retry")
        graph.add_conditional_edges(
            "commit_or_retry",
            self._route_after_commit,
            {"retrieve_context": "retrieve_context", "finalize": "finalize"},
        )
        graph.add_edge("finalize", END)
        return graph.compile()

    def _load_context(self, state: GraphState) -> GraphState:
        return state

    def _retrieve_context(self, state: GraphState) -> GraphState:
        query = state["user_goal"]
        if state.get("plan_steps"):
            current_step = state["plan_steps"][state["current_step"]]
            query = current_step.objective
        hits = self.retrieval_service.retrieve(query)
        state["retrieval_hits"] = hits
        return state

    def _route_after_retrieve(self, state: GraphState) -> str:
        return "plan" if not state.get("plan_steps") else "execute_step"

    def _plan(self, state: GraphState) -> GraphState:
        steps = self.planner.plan(
            user_goal=state["user_goal"],
            retrieval_hits=state.get("retrieval_hits", []),
            message_history=state.get("messages", []),
        )
        state["plan_steps"] = steps
        state["current_step"] = 0
        state["retries"] = 0
        return state

    def _execute_step(self, state: GraphState) -> GraphState:
        step = state["plan_steps"][state["current_step"]]
        result = self.executor.execute(
            step=step,
            retrieval_hits=state.get("retrieval_hits", []),
            message_history=state.get("messages", []),
        )
        state["messages"] = result.messages
        state["current_output"] = result.final_output
        state["current_tool_results"] = result.tool_results
        state["artifacts"] = {
            **state.get("artifacts", {}),
            step.id: {
                "artifacts": result.artifacts,
                "final_output": result.final_output,
            },
        }
        return state

    def _review_step(self, state: GraphState) -> GraphState:
        step = state["plan_steps"][state["current_step"]]
        decision = self.reviewer.review(
            user_goal=state["user_goal"],
            step_title=step.title,
            step_output=state.get("current_output", ""),
            tool_results=state.get("current_tool_results", []),
        )
        state["review_notes"] = decision.rationale
        state["decision"] = {
            "accept": "continue",
            "revise": "retry",
            "abort": "abort",
        }[decision.outcome]
        return state

    def _commit_or_retry(self, state: GraphState) -> GraphState:
        session_id = state["session_id"]
        step = state["plan_steps"][state["current_step"]]
        self.repository.record_event(
            session_id,
            "step_reviewed",
            {
                "step_id": step.id,
                "decision": state["decision"],
                "review_notes": state.get("review_notes"),
            },
        )

        for artifact_path in state.get("artifacts", {}).get(step.id, {}).get("artifacts", []):
            self.repository.record_artifact(
                session_id,
                kind="file",
                path=artifact_path,
                metadata={"step_id": step.id},
            )

        if state["decision"] == "retry":
            state["retries"] = state.get("retries", 0) + 1
            if state["retries"] > self.max_retries:
                state["decision"] = "abort"
                state["final_output"] = state.get("current_output", "")
        elif state["decision"] == "continue":
            state["retries"] = 0
            if state["current_step"] >= len(state["plan_steps"]) - 1:
                state["decision"] = "done"
                state["final_output"] = state.get("current_output", "")
            else:
                state["current_step"] += 1

        self.repository.save_checkpoint(_graph_state_to_agent_state(state))
        return state

    def _route_after_commit(self, state: GraphState) -> str:
        return "finalize" if state["decision"] in {"done", "abort"} else "retrieve_context"

    def _finalize(self, state: GraphState) -> GraphState:
        self.repository.record_event(
            state["session_id"],
            "task_finalized",
            {
                "decision": state["decision"],
                "final_output": state.get("final_output", ""),
            },
        )
        if state.get("final_output"):
            self.repository.append_message(
                state["session_id"],
                Message(role="assistant", content=state["final_output"]),
            )
        return state

    def _finalize_result(self, state: GraphState) -> OrchestratorResult:
        return OrchestratorResult(
            session_id=state["session_id"],
            final_output=state.get("final_output", ""),
            final_state=state,
        )


def _graph_state_to_agent_state(state: GraphState) -> AgentState:
    return AgentState(
        session_id=state["session_id"],
        user_goal=state["user_goal"],
        messages=state.get("messages", []),
        plan_steps=state.get("plan_steps", []),
        current_step=state.get("current_step", 0),
        retrieval_hits=[
            asdict(hit) if is_dataclass(hit) else hit
            for hit in state.get("retrieval_hits", [])
        ],
        artifacts=state.get("artifacts", {}),
        review_notes=state.get("review_notes"),
        decision=state.get("decision", "continue"),
        trace_id=state.get("trace_id"),
    )


def _agent_state_to_graph_state(state: AgentState) -> GraphState:
    retrieval_hits = [
        RetrievalHit(**hit) if isinstance(hit, dict) and {"path", "line_start", "line_end", "snippet", "score", "reason"} <= set(hit)
        else hit
        for hit in state.retrieval_hits
    ]
    return GraphState(
        session_id=state.session_id,
        user_goal=state.user_goal,
        messages=state.messages,
        plan_steps=state.plan_steps,
        current_step=state.current_step,
        retrieval_hits=retrieval_hits,
        artifacts=state.artifacts,
        review_notes=state.review_notes,
        decision=state.decision,
        trace_id=state.trace_id or str(uuid4()),
        retries=0,
        current_output="",
        current_tool_results=[],
        final_output="",
    )
