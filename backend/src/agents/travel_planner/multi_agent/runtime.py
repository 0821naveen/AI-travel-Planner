from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FutureTimeoutError
from copy import deepcopy
from typing import Callable, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.travel_planner.multi_agent.adapters import (
    _confidence_for_role,
    build_specialist_adapters,
    clear_dependent_artifacts_for_itinerary_revision,
)
from src.agents.travel_planner.multi_agent.coordinator import CoordinatorAgent, CoordinatorDecision
from src.agents.travel_planner.multi_agent.schemas import (
    AgentMessage,
    AgentRole,
    AgentTaskStatus,
    CoordinationLedger,
    MessageKind,
)
from src.agents.travel_planner.multi_agent.topology import build_initial_coordination_ledger
from src.agents.travel_planner.schemas import TripRequest, TripStatus
from src.agents.travel_planner.state import PlannerContext
from src.core.config import get_settings
from src.core.logging import get_logger


class MultiAgentState(TypedDict):
    context: PlannerContext
    ledger: CoordinationLedger
    decision: Optional[CoordinatorDecision]
    terminal_reason: Optional[str]
    progress_callback: Optional[Callable[[dict[str, object]], None]]


class CoordinatorRuntime:
    def __init__(self) -> None:
        self.coordinator = CoordinatorAgent()
        self.adapters = build_specialist_adapters()
        self.logger = get_logger("travel_planner.multi_agent_runtime")
        self.app = self._build_graph()

    def bootstrap_trip(self, trip_id: str, request: TripRequest, *, run_id: str | None = None) -> MultiAgentState:
        return self.bootstrap_trip_with_progress(trip_id, request, run_id=run_id, progress_callback=None)

    def bootstrap_trip_with_progress(
        self,
        trip_id: str,
        request: TripRequest,
        *,
        run_id: str | None = None,
        progress_callback: Optional[Callable[[dict[str, object]], None]] = None,
    ) -> MultiAgentState:
        context = PlannerContext(trip_id=trip_id, request=request, run_id=run_id, status=TripStatus.DRAFT)
        ledger = build_initial_coordination_ledger(trip_id, request)
        initial_state: MultiAgentState = {
            "context": context,
            "ledger": ledger,
            "decision": None,
            "terminal_reason": None,
            "progress_callback": progress_callback,
        }
        return self.app.invoke(initial_state, config={"recursion_limit": max(50, ledger.max_iterations * 4)})

    def _build_graph(self):
        graph = StateGraph(MultiAgentState)
        graph.add_node("coordinator", self._coordinator_node)
        graph.add_node("parallel_batch", self._parallel_batch_node)

        for role in self.adapters:
            graph.add_node(role.value, self._specialist_node(role))

        graph.add_edge(START, "coordinator")
        graph.add_conditional_edges(
            "coordinator",
            self._route_from_decision,
            {
                "clarification": AgentRole.CLARIFICATION.value,
                "destination_research": AgentRole.DESTINATION_RESEARCH.value,
                "itinerary": AgentRole.ITINERARY.value,
                "stay": AgentRole.STAY.value,
                "transport": AgentRole.TRANSPORT.value,
                "food": AgentRole.FOOD.value,
                "budget": AgentRole.BUDGET.value,
                "safety": AgentRole.SAFETY.value,
                "review": AgentRole.REVIEW.value,
                "governance": AgentRole.GOVERNANCE.value,
                "parallel_batch": "parallel_batch",
                "end": END,
            },
        )

        for role in self.adapters:
            graph.add_edge(role.value, "coordinator")
        graph.add_edge("parallel_batch", "coordinator")

        return graph.compile()

    def _coordinator_node(self, state: MultiAgentState) -> MultiAgentState:
        context = state["context"]
        ledger = state["ledger"]
        decision = self.coordinator.run(ledger, context)
        next_roles = [role.value for role in decision.next_roles]
        self._emit_progress(
            state,
            event_type="coordinator_decision",
            step_name="coordinator_agent",
            status="running",
            next_roles=next_roles,
            task_ids=list(decision.task_ids),
            terminal=decision.terminal,
            waiting_for_user=decision.waiting_for_user,
            rationale=decision.rationale,
            summary=(
                f"Coordinator routed the workflow to {self._format_role_batch(decision.next_roles)}."
                if next_roles
                else "Coordinator concluded that no further specialist work was required."
            ),
        )
        self.logger.info(
            "multi_agent.coordinator.decision",
            extra={
                "trip_id": context.trip_id,
                "run_id": context.run_id,
                "status": context.status.value,
                "iteration_count": ledger.iteration_count,
                "next_roles": [role.value for role in decision.next_roles],
                "task_ids": list(decision.task_ids),
                "terminal": decision.terminal,
            },
        )

        if decision.next_role == AgentRole.ITINERARY and (
            context.budget_assessment is not None or context.review_assessment is not None
        ):
            clear_dependent_artifacts_for_itinerary_revision(ledger, context)
            itinerary_task = next(task for task in ledger.task_board if task.task_id == "draft_itinerary")
            itinerary_task.status = AgentTaskStatus.NEEDS_REVISION

        self.coordinator.record_assignment(ledger, decision)
        terminal_reason = decision.rationale if decision.terminal else None
        return {
            "context": context,
            "ledger": ledger,
            "decision": decision,
            "terminal_reason": terminal_reason,
            "progress_callback": state["progress_callback"],
        }

    def _specialist_node(self, role: AgentRole):
        adapter = self.adapters[role]

        def _runner(state: MultiAgentState) -> MultiAgentState:
            self._emit_progress(
                state,
                event_type="specialist_started",
                step_name=role.value,
                status="running",
                task_id=adapter.task_id,
                summary=f"{self._format_role_name(role)} started working on its assigned task.",
            )
            self.logger.info(
                "multi_agent.specialist.started",
                extra={
                    "trip_id": state["context"].trip_id,
                    "run_id": state["context"].run_id,
                    "node_name": role.value,
                    "task_id": adapter.task_id,
                },
            )
            context = adapter.run(state["ledger"], state["context"])
            self._emit_progress(
                state,
                event_type="specialist_completed",
                step_name=role.value,
                status="succeeded",
                task_id=adapter.task_id,
                summary=adapter.summary_builder(context),
                confidence=_confidence_for_role(role, context),
            )
            self.logger.info(
                "multi_agent.specialist.completed",
                extra={
                    "trip_id": context.trip_id,
                    "run_id": context.run_id,
                    "node_name": role.value,
                    "task_id": adapter.task_id,
                    "status": context.status.value,
                },
            )
            return {
                "context": context,
                "ledger": state["ledger"],
                "decision": state["decision"],
                "terminal_reason": state["terminal_reason"],
                "progress_callback": state["progress_callback"],
            }

        return _runner

    def _parallel_batch_node(self, state: MultiAgentState) -> MultiAgentState:
        decision = state["decision"]
        if decision is None:
            return state
        ledger = state["ledger"]
        base_context = state["context"]
        batch_timeout_seconds = max(45, get_settings().provider_runtime.request_timeout_seconds * 2)
        self.logger.info(
            "multi_agent.parallel_batch.started",
            extra={
                "trip_id": base_context.trip_id,
                "run_id": base_context.run_id,
                "roles": [role.value for role in decision.next_roles],
                "task_ids": list(decision.task_ids),
                "timeout_seconds": batch_timeout_seconds,
            },
        )
        self._emit_progress(
            state,
            event_type="parallel_batch_started",
            step_name="parallel_batch",
            status="running",
            roles=[role.value for role in decision.next_roles],
            task_ids=list(decision.task_ids),
            summary=f"Coordinator released {self._format_role_batch(decision.next_roles)} in parallel to reduce latency.",
        )

        def _run_adapter(role: AgentRole):
            adapter = self.adapters[role]
            context_copy = deepcopy(base_context)
            result_context = adapter.runner(context_copy)
            return role, result_context

        executor = ThreadPoolExecutor(max_workers=len(decision.next_roles))
        future_map = {executor.submit(_run_adapter, role): role for role in decision.next_roles}
        results = []
        try:
            for future in as_completed(future_map, timeout=batch_timeout_seconds):
                role = future_map[future]
                try:
                    results.append(future.result())
                    self.logger.info(
                        "multi_agent.parallel_batch.specialist_completed",
                        extra={
                            "trip_id": base_context.trip_id,
                            "run_id": base_context.run_id,
                            "node_name": role.value,
                        },
                    )
                    self._emit_progress(
                        state,
                        event_type="specialist_completed",
                        step_name=role.value,
                        status="succeeded",
                        task_id=self.adapters[role].task_id,
                    )
                except Exception as exc:
                    self.logger.exception(
                        "multi_agent.parallel_batch.specialist_failed",
                        extra={
                            "trip_id": base_context.trip_id,
                            "run_id": base_context.run_id,
                            "node_name": role.value,
                        },
                    )
                    raise RuntimeError(f"Parallel specialist '{role.value}' failed: {exc}") from exc
        except FutureTimeoutError as exc:
            unresolved = [role.value for future, role in future_map.items() if not future.done()]
            self.logger.error(
                "multi_agent.parallel_batch.timeout",
                extra={
                    "trip_id": base_context.trip_id,
                    "run_id": base_context.run_id,
                    "roles": [role.value for role in decision.next_roles],
                    "unresolved_roles": unresolved,
                    "timeout_seconds": batch_timeout_seconds,
                },
            )
            raise RuntimeError(
                "Parallel specialist batch timed out after "
                f"{batch_timeout_seconds}s; unresolved roles: {', '.join(unresolved)}"
            ) from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        merged_context = base_context
        for role, result_context in results:
            adapter = self.adapters[role]
            self._merge_context(merged_context, result_context, role)
            task = next(task for task in ledger.task_board if task.task_id == adapter.task_id)
            task.status = AgentTaskStatus.COMPLETED
            artifact = self._artifact_for_role(role, merged_context)
            if artifact is not None:
                ledger.artifacts[adapter.artifact_key] = artifact
            ledger.message_log.append(
                self._build_result_message(ledger, adapter, role, merged_context)
            )

        ledger.active_role = AgentRole.COORDINATOR
        self.logger.info(
            "multi_agent.parallel_batch.completed",
            extra={
                "trip_id": merged_context.trip_id,
                "run_id": merged_context.run_id,
                "roles": [role.value for role, _ in results],
                "status": merged_context.status.value,
            },
        )
        self._emit_progress(
            state,
            event_type="parallel_batch_completed",
            step_name="parallel_batch",
            status="succeeded",
            roles=[role.value for role, _ in results],
            summary=f"Parallel specialist batch finished for {self._format_role_batch([role for role, _ in results])}.",
        )
        return {
            "context": merged_context,
            "ledger": ledger,
            "decision": state["decision"],
            "terminal_reason": state["terminal_reason"],
            "progress_callback": state["progress_callback"],
        }

    def _route_from_decision(self, state: MultiAgentState) -> str:
        decision = state["decision"]
        if decision is None or decision.terminal or decision.next_role is None:
            return "end"
        if decision.is_parallel_batch:
            return "parallel_batch"
        return decision.next_role.value

    def _emit_progress(self, state: MultiAgentState, **payload: object) -> None:
        callback = state.get("progress_callback")
        if callback is None:
            return
        callback(payload)

    def _merge_context(self, target: PlannerContext, source: PlannerContext, role: AgentRole) -> None:
        if role == AgentRole.STAY:
            target.stay_recommendation_plan = source.stay_recommendation_plan
        elif role == AgentRole.TRANSPORT:
            target.local_transport_plan = source.local_transport_plan
        elif role == AgentRole.FOOD:
            target.food_recommendation_plan = source.food_recommendation_plan
        elif role == AgentRole.SAFETY:
            target.solo_women_safety_assessment = source.solo_women_safety_assessment
        for step in source.route_trace:
            if step not in target.route_trace:
                target.route_trace.append(step)
        target.status = source.status

    def _artifact_for_role(self, role: AgentRole, context: PlannerContext):
        if role == AgentRole.STAY and context.stay_recommendation_plan is not None:
            return context.stay_recommendation_plan.model_dump(mode="json")
        if role == AgentRole.TRANSPORT and context.local_transport_plan is not None:
            return context.local_transport_plan.model_dump(mode="json")
        if role == AgentRole.FOOD and context.food_recommendation_plan is not None:
            return context.food_recommendation_plan.model_dump(mode="json")
        if role == AgentRole.SAFETY and context.solo_women_safety_assessment is not None:
            return context.solo_women_safety_assessment.model_dump(mode="json")
        return None

    def _build_result_message(self, ledger, adapter, role: AgentRole, context: PlannerContext):
        return AgentMessage(
            message_id=f"result-{ledger.iteration_count}-{adapter.task_id}",
            kind=MessageKind.TASK_RESULT,
            sender_role=role,
            recipient_role=AgentRole.COORDINATOR,
            task_id=adapter.task_id,
            summary=adapter.summary_builder(context),
            payload={"status": context.status.value},
            artifact_keys=[adapter.artifact_key],
            confidence=_confidence_for_role(role, context),
        )

    def _format_role_name(self, role: AgentRole) -> str:
        return role.value.replace("_", " ").title()

    def _format_role_batch(self, roles: list[AgentRole]) -> str:
        labels = [self._format_role_name(role) for role in roles]
        if not labels:
            return "no specialists"
        if len(labels) == 1:
            return labels[0]
        if len(labels) == 2:
            return f"{labels[0]} and {labels[1]}"
        return f"{', '.join(labels[:-1])}, and {labels[-1]}"
