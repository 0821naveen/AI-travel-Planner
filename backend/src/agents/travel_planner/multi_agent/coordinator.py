from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from src.agents.travel_planner.multi_agent.schemas import AgentMessage, AgentRole, AgentTaskStatus, MessageKind
from src.agents.travel_planner.multi_agent.topology import build_default_agent_specs
from src.agents.travel_planner.state import PlannerContext

PARALLEL_SPECIALIST_ROLES = {
    AgentRole.STAY,
    AgentRole.TRANSPORT,
    AgentRole.FOOD,
    AgentRole.SAFETY,
}


class CoordinatorDecision(BaseModel):
    next_roles: list[AgentRole] = []
    task_ids: list[str] = []
    rationale: str
    terminal: bool = False
    waiting_for_user: bool = False

    @property
    def is_parallel_batch(self) -> bool:
        return len(self.next_roles) > 1

    @property
    def next_role(self) -> Optional[AgentRole]:
        return self.next_roles[0] if self.next_roles else None

    @property
    def task_id(self) -> Optional[str]:
        return self.task_ids[0] if self.task_ids else None


class CoordinatorAgent:
    """Decision-maker for the multi-agent runtime.

    This is intentionally custom logic: it decides who should act next, when
    a revision is needed, and when the run should stop or escalate. LangGraph
    handles orchestration mechanics around this policy layer.
    """

    name: str = "coordinator_agent"

    def run(self, ledger, context: PlannerContext) -> CoordinatorDecision:
        ledger.iteration_count += 1
        if ledger.iteration_count > ledger.max_iterations:
            return CoordinatorDecision(
                rationale="Maximum coordination iterations reached. Stop and escalate for review.",
                terminal=True,
            )

        if context.status.value == "awaiting_clarification":
            return CoordinatorDecision(
                rationale="Blocking clarification questions remain. Pause autonomous planning until user input arrives.",
                terminal=True,
                waiting_for_user=True,
            )

        itinerary_task = self._task(ledger, "draft_itinerary")
        if (
            context.budget_assessment is not None
            and not context.budget_assessment.within_budget
            and itinerary_task is not None
            and itinerary_task.revision_count < itinerary_task.max_revision_rounds
        ):
            return CoordinatorDecision(
                next_roles=[AgentRole.ITINERARY],
                task_ids=[itinerary_task.task_id],
                rationale="Budget agent reported an over-budget plan. Request itinerary revision before final review.",
            )

        if (
            context.review_assessment is not None
            and not context.review_assessment.approved
            and itinerary_task is not None
            and itinerary_task.revision_count < itinerary_task.max_revision_rounds
            and context.budget_assessment is not None
            and context.budget_assessment.within_budget
        ):
            return CoordinatorDecision(
                next_roles=[AgentRole.ITINERARY],
                task_ids=[itinerary_task.task_id],
                rationale="Review found unresolved issues. Request one bounded itinerary revision before governance.",
            )

        parallel_tasks = [
            task
            for task in ledger.task_board
            if task.owner_role in PARALLEL_SPECIALIST_ROLES
            and task.status in {AgentTaskStatus.PENDING, AgentTaskStatus.NEEDS_REVISION}
            and self._dependencies_complete(ledger, task.depends_on)
        ]
        if len(parallel_tasks) > 1:
            return CoordinatorDecision(
                next_roles=[task.owner_role for task in parallel_tasks],
                task_ids=[task.task_id for task in parallel_tasks],
                rationale="Multiple independent specialist tasks are ready. Run them in parallel to reduce wall-clock latency.",
            )

        for task in ledger.task_board:
            if task.status not in {AgentTaskStatus.PENDING, AgentTaskStatus.NEEDS_REVISION}:
                continue
            if not self._dependencies_complete(ledger, task.depends_on):
                continue
            return CoordinatorDecision(
                next_roles=[task.owner_role],
                task_ids=[task.task_id],
                rationale=f"Task '{task.title}' is the next executable specialist task.",
            )

        return CoordinatorDecision(
            rationale="All executable specialist tasks are complete. Stop coordinator loop.",
            terminal=True,
        )

    def record_assignment(self, ledger, decision: CoordinatorDecision) -> None:
        if not decision.next_roles or not decision.task_ids:
            return
        ledger.active_role = decision.next_role or AgentRole.COORDINATOR
        for role, task_id in zip(decision.next_roles, decision.task_ids):
            task = self._task(ledger, task_id)
            if task is None:
                continue
            if task.status == AgentTaskStatus.NEEDS_REVISION:
                task.revision_count += 1
            task.status = AgentTaskStatus.IN_PROGRESS
            ledger.message_log.append(
                AgentMessage(
                    message_id=f"assignment-{ledger.iteration_count}-{task_id}",
                    kind=MessageKind.TASK_ASSIGNMENT,
                    sender_role=AgentRole.COORDINATOR,
                    recipient_role=role,
                    task_id=task_id,
                    summary=decision.rationale,
                    payload={"role_spec": build_default_agent_specs()[role].purpose},
                    requires_response=True,
                )
            )

    def _dependencies_complete(self, ledger, dependency_ids: list[str]) -> bool:
        for dependency_id in dependency_ids:
            dependency = self._task(ledger, dependency_id)
            if dependency is None or dependency.status != AgentTaskStatus.COMPLETED:
                return False
        return True

    def _task(self, ledger, task_id: str):
        return next((task for task in ledger.task_board if task.task_id == task_id), None)
