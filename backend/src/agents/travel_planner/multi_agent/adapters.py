from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from src.agents.travel_planner.governance import evaluate_governance
from src.agents.travel_planner.multi_agent.schemas import AgentMessage, AgentRole, AgentTaskStatus, MessageKind
from src.agents.travel_planner.nodes import (
    BudgetOptimizationAgent,
    ClarificationValidator,
    DestinationResearchAgent,
    FoodRecommendationAgent,
    GovernanceGateAgent,
    ItineraryPlanningAgent,
    LocalTransportAgent,
    ResearchSignalAgent,
    ReviewAndConsistencyAgent,
    SoloWomenSafetyAdvisorAgent,
    StayRecommendationAgent,
)
from src.agents.travel_planner.state import PlannerContext


@dataclass
class SpecialistAdapter:
    role: AgentRole
    task_id: str
    artifact_key: str
    runner: Callable[[PlannerContext], PlannerContext]
    summary_builder: Callable[[PlannerContext], str]

    def run(self, ledger, context: PlannerContext) -> PlannerContext:
        updated = self.runner(context)
        task = next(task for task in ledger.task_board if task.task_id == self.task_id)
        task.status = AgentTaskStatus.COMPLETED
        ledger.active_role = AgentRole.COORDINATOR
        summary = self.summary_builder(updated)
        artifact = _artifact_for_role(self.role, updated)
        if artifact is not None:
            ledger.artifacts[self.artifact_key] = artifact
        if self.role == AgentRole.CLARIFICATION:
            ledger.open_questions = [item.question for item in updated.clarification_questions]
        if self.role == AgentRole.GOVERNANCE:
            ledger.governance_flags = list(updated.governance_flags)
        ledger.message_log.append(
            AgentMessage(
                message_id=f"result-{ledger.iteration_count}-{self.task_id}",
                kind=MessageKind.TASK_RESULT,
                sender_role=self.role,
                recipient_role=AgentRole.COORDINATOR,
                task_id=self.task_id,
                summary=summary,
                payload={"status": updated.status.value},
                artifact_keys=[self.artifact_key],
                confidence=_confidence_for_role(self.role, updated),
            )
        )
        return updated


def build_specialist_adapters() -> dict[AgentRole, SpecialistAdapter]:
    clarification = ClarificationValidator()
    research_signal = ResearchSignalAgent()
    destination_research = DestinationResearchAgent()
    itinerary = ItineraryPlanningAgent()
    stay = StayRecommendationAgent()
    transport = LocalTransportAgent()
    food = FoodRecommendationAgent()
    budget = BudgetOptimizationAgent()
    safety = SoloWomenSafetyAdvisorAgent()
    review = ReviewAndConsistencyAgent()
    governance = GovernanceGateAgent()

    return {
        AgentRole.CLARIFICATION: SpecialistAdapter(
            role=AgentRole.CLARIFICATION,
            task_id="clarify_request",
            artifact_key="clarification_questions",
            runner=clarification.run,
            summary_builder=lambda context: f"Clarification produced {len(context.clarification_questions)} question(s).",
        ),
        AgentRole.DESTINATION_RESEARCH: SpecialistAdapter(
            role=AgentRole.DESTINATION_RESEARCH,
            task_id="research_destination",
            artifact_key="destination_research",
            runner=lambda context: destination_research.run(research_signal.run(context)),
            summary_builder=lambda context: context.destination_research.summary if context.destination_research else "Destination research missing.",
        ),
        AgentRole.ITINERARY: SpecialistAdapter(
            role=AgentRole.ITINERARY,
            task_id="draft_itinerary",
            artifact_key="itinerary_plan",
            runner=itinerary.run,
            summary_builder=lambda context: context.itinerary_plan.summary if context.itinerary_plan else "Itinerary missing.",
        ),
        AgentRole.STAY: SpecialistAdapter(
            role=AgentRole.STAY,
            task_id="recommend_stay",
            artifact_key="stay_recommendation_plan",
            runner=stay.run,
            summary_builder=lambda context: context.stay_recommendation_plan.summary if context.stay_recommendation_plan else "Stay plan missing.",
        ),
        AgentRole.TRANSPORT: SpecialistAdapter(
            role=AgentRole.TRANSPORT,
            task_id="plan_transport",
            artifact_key="local_transport_plan",
            runner=transport.run,
            summary_builder=lambda context: context.local_transport_plan.summary if context.local_transport_plan else "Transport plan missing.",
        ),
        AgentRole.FOOD: SpecialistAdapter(
            role=AgentRole.FOOD,
            task_id="recommend_food",
            artifact_key="food_recommendation_plan",
            runner=food.run,
            summary_builder=lambda context: context.food_recommendation_plan.summary if context.food_recommendation_plan else "Food plan missing.",
        ),
        AgentRole.BUDGET: SpecialistAdapter(
            role=AgentRole.BUDGET,
            task_id="audit_budget",
            artifact_key="budget_assessment",
            runner=budget.run,
            summary_builder=lambda context: context.budget_assessment.summary if context.budget_assessment else "Budget assessment missing.",
        ),
        AgentRole.SAFETY: SpecialistAdapter(
            role=AgentRole.SAFETY,
            task_id="review_safety",
            artifact_key="solo_women_safety_assessment",
            runner=safety.run,
            summary_builder=lambda context: (
                context.solo_women_safety_assessment.summary if context.solo_women_safety_assessment else "Safety assessment missing."
            ),
        ),
        AgentRole.REVIEW: SpecialistAdapter(
            role=AgentRole.REVIEW,
            task_id="critique_plan",
            artifact_key="review_assessment",
            runner=review.run,
            summary_builder=lambda context: context.review_assessment.summary if context.review_assessment else "Review assessment missing.",
        ),
        AgentRole.GOVERNANCE: SpecialistAdapter(
            role=AgentRole.GOVERNANCE,
            task_id="govern_plan",
            artifact_key="governance_decision",
            runner=governance.run,
            summary_builder=lambda context: (
                "Governance approved the plan."
                if context.review_assessment is not None and context.review_assessment.approved
                else "Governance left the plan in review."
            ),
        ),
    }


def clear_dependent_artifacts_for_itinerary_revision(ledger, context: PlannerContext) -> None:
    for task_id in [
        "recommend_stay",
        "plan_transport",
        "recommend_food",
        "audit_budget",
        "review_safety",
        "critique_plan",
        "govern_plan",
    ]:
        task = next(task for task in ledger.task_board if task.task_id == task_id)
        task.status = AgentTaskStatus.PENDING

    context.stay_recommendation_plan = None
    context.local_transport_plan = None
    context.food_recommendation_plan = None
    context.budget_assessment = None
    context.solo_women_safety_assessment = None
    context.review_assessment = None
    context.governance_flags = []
    ledger.governance_flags = []
    for artifact_key in [
        "stay_recommendation_plan",
        "local_transport_plan",
        "food_recommendation_plan",
        "budget_assessment",
        "solo_women_safety_assessment",
        "review_assessment",
        "governance_decision",
    ]:
        ledger.artifacts.pop(artifact_key, None)


def _artifact_for_role(role: AgentRole, context: PlannerContext) -> Optional[dict]:
    if role == AgentRole.CLARIFICATION:
        return {
            "questions": [item.model_dump(mode="json") for item in context.clarification_questions],
            "status": context.status.value,
        }
    if role == AgentRole.DESTINATION_RESEARCH and context.destination_research is not None:
        return context.destination_research.model_dump(mode="json")
    if role == AgentRole.ITINERARY and context.itinerary_plan is not None:
        return context.itinerary_plan.model_dump(mode="json")
    if role == AgentRole.STAY and context.stay_recommendation_plan is not None:
        return context.stay_recommendation_plan.model_dump(mode="json")
    if role == AgentRole.TRANSPORT and context.local_transport_plan is not None:
        return context.local_transport_plan.model_dump(mode="json")
    if role == AgentRole.FOOD and context.food_recommendation_plan is not None:
        return context.food_recommendation_plan.model_dump(mode="json")
    if role == AgentRole.BUDGET and context.budget_assessment is not None:
        return context.budget_assessment.model_dump(mode="json")
    if role == AgentRole.SAFETY and context.solo_women_safety_assessment is not None:
        return context.solo_women_safety_assessment.model_dump(mode="json")
    if role == AgentRole.REVIEW and context.review_assessment is not None:
        return context.review_assessment.model_dump(mode="json")
    if role == AgentRole.GOVERNANCE:
        decision = evaluate_governance(context)
        return {"approve": decision.approve, "flags": decision.flags}
    return None


def _confidence_for_role(role: AgentRole, context: PlannerContext) -> float:
    if role == AgentRole.DESTINATION_RESEARCH and context.destination_research is not None:
        return context.destination_research.confidence
    if role == AgentRole.ITINERARY and context.itinerary_plan is not None:
        return context.itinerary_plan.confidence
    if role == AgentRole.STAY and context.stay_recommendation_plan is not None:
        return context.stay_recommendation_plan.confidence
    if role == AgentRole.TRANSPORT and context.local_transport_plan is not None:
        return context.local_transport_plan.confidence
    if role == AgentRole.FOOD and context.food_recommendation_plan is not None:
        return context.food_recommendation_plan.confidence
    if role == AgentRole.BUDGET and context.budget_assessment is not None:
        return context.budget_assessment.confidence
    if role == AgentRole.SAFETY and context.solo_women_safety_assessment is not None:
        return context.solo_women_safety_assessment.confidence
    if role == AgentRole.REVIEW and context.review_assessment is not None:
        return context.review_assessment.confidence
    return 1.0
