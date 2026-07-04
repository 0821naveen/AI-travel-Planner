from __future__ import annotations

from pydantic import BaseModel

from src.agents.travel_planner.multi_agent.schemas import (
    AgentRole,
    AgentTask,
    CoordinationLedger,
    SharedObjective,
)
from src.agents.travel_planner.schemas import TripRequest


class AgentSpec(BaseModel):
    role: AgentRole
    purpose: str
    allowed_tools: tuple[str, ...] = ()
    can_delegate_to: tuple[AgentRole, ...] = ()
    produces_artifacts: tuple[str, ...] = ()
    stop_condition: str


def build_default_agent_specs() -> dict[AgentRole, AgentSpec]:
    return {
        AgentRole.COORDINATOR: AgentSpec(
            role=AgentRole.COORDINATOR,
            purpose="Own the trip objective, choose which specialist acts next, and stop when the plan is review-ready.",
            can_delegate_to=(
                AgentRole.CLARIFICATION,
                AgentRole.DESTINATION_RESEARCH,
                AgentRole.ITINERARY,
                AgentRole.STAY,
                AgentRole.TRANSPORT,
                AgentRole.FOOD,
                AgentRole.BUDGET,
                AgentRole.SAFETY,
                AgentRole.REVIEW,
                AgentRole.GOVERNANCE,
            ),
            produces_artifacts=("coordination_decision", "task_plan"),
            stop_condition="Every required artifact exists and governance has either approved or escalated to a human.",
        ),
        AgentRole.CLARIFICATION: AgentSpec(
            role=AgentRole.CLARIFICATION,
            purpose="Identify the minimum unanswered questions that block safe planning.",
            produces_artifacts=("clarification_questions",),
            stop_condition="Either no blocking questions remain or the request has been paused for user clarification.",
        ),
        AgentRole.DESTINATION_RESEARCH: AgentSpec(
            role=AgentRole.DESTINATION_RESEARCH,
            purpose="Build the researched destination brief, source list, risks, and planning assumptions.",
            allowed_tools=("weather_lookup", "web_search", "google_flights_search", "flight_schedule_lookup", "json_completion"),
            produces_artifacts=("destination_research",),
            stop_condition="Destination context is sufficient for itinerary drafting or the gaps are explicitly reported.",
        ),
        AgentRole.ITINERARY: AgentSpec(
            role=AgentRole.ITINERARY,
            purpose="Draft and revise the day-by-day itinerary from the shared objective and research evidence.",
            allowed_tools=("json_completion",),
            can_delegate_to=(AgentRole.DESTINATION_RESEARCH,),
            produces_artifacts=("itinerary_plan",),
            stop_condition="The itinerary satisfies pace, duration, and destination-fit criteria.",
        ),
        AgentRole.STAY: AgentSpec(
            role=AgentRole.STAY,
            purpose="Recommend accommodation areas and options that fit the itinerary shape.",
            allowed_tools=("web_search", "google_hotels_search", "json_completion"),
            produces_artifacts=("stay_recommendation_plan",),
            stop_condition="Stay guidance aligns to itinerary areas, budget tier, and traveler profile.",
        ),
        AgentRole.TRANSPORT: AgentSpec(
            role=AgentRole.TRANSPORT,
            purpose="Resolve airport, inter-area, and daily movement guidance with fallback modes.",
            allowed_tools=("json_completion",),
            produces_artifacts=("local_transport_plan",),
            stop_condition="Each critical movement leg has a recommended mode, backup mode, and timing signal.",
        ),
        AgentRole.FOOD: AgentSpec(
            role=AgentRole.FOOD,
            purpose="Attach meal guidance, restaurant ideas, and dish recommendations to the itinerary.",
            allowed_tools=("json_completion", "youtube_video_details"),
            produces_artifacts=("food_recommendation_plan",),
            stop_condition="The itinerary has meal guidance that respects dietary and area constraints.",
        ),
        AgentRole.BUDGET: AgentSpec(
            role=AgentRole.BUDGET,
            purpose="Estimate spend, identify cost drivers, and request revisions when the plan misses the budget target.",
            allowed_tools=("json_completion",),
            can_delegate_to=(AgentRole.ITINERARY, AgentRole.STAY, AgentRole.TRANSPORT, AgentRole.FOOD),
            produces_artifacts=("budget_assessment",),
            stop_condition="Budget fit is either acceptable or the exact reasons for overrun are documented.",
        ),
        AgentRole.SAFETY: AgentSpec(
            role=AgentRole.SAFETY,
            purpose="Review the trip for traveler-safety guidance and specific situational risks.",
            allowed_tools=("json_completion",),
            produces_artifacts=("solo_women_safety_assessment",),
            stop_condition="Material safety warnings and mitigations are captured for the itinerary.",
        ),
        AgentRole.REVIEW: AgentSpec(
            role=AgentRole.REVIEW,
            purpose="Critique the assembled plan for consistency, confidence, and unsupported assumptions.",
            allowed_tools=("json_completion",),
            can_delegate_to=(
                AgentRole.ITINERARY,
                AgentRole.STAY,
                AgentRole.TRANSPORT,
                AgentRole.FOOD,
                AgentRole.BUDGET,
                AgentRole.SAFETY,
            ),
            produces_artifacts=("review_assessment",),
            stop_condition="The plan has either passed review or emitted concrete revision requests.",
        ),
        AgentRole.GOVERNANCE: AgentSpec(
            role=AgentRole.GOVERNANCE,
            purpose="Apply policy, confidence, and escalation rules before completion.",
            produces_artifacts=("governance_decision",),
            stop_condition="The plan is either approved for completion or escalated with explicit flags.",
        ),
        AgentRole.HUMAN_OPERATOR: AgentSpec(
            role=AgentRole.HUMAN_OPERATOR,
            purpose="Resolve escalations that should not be auto-approved by the system.",
            produces_artifacts=("human_approval",),
            stop_condition="A human has approved, rejected, or requested changes.",
        ),
    }


def delegation_allowed(from_role: AgentRole, to_role: AgentRole) -> bool:
    spec = build_default_agent_specs()[from_role]
    return to_role in spec.can_delegate_to


def build_initial_coordination_ledger(trip_id: str, request: TripRequest) -> CoordinationLedger:
    objective = SharedObjective(
        trip_id=trip_id,
        user_goal=f"Plan a {request.trip_purpose.value} trip to {request.destination} from {request.start_date} to {request.end_date}.",
        success_criteria=[
            "Produce an itinerary, stay plan, local transport guidance, food recommendations, budget assessment, and review summary.",
            "Keep the plan aligned to traveler count, pace, interests, and stated preferences.",
            "Document risks, assumptions, and confidence gaps before completion.",
        ],
        hard_constraints=[
            f"Total budget target: {request.total_budget}",
            f"Traveler count: {request.traveler_count}",
            f"Budget tier: {request.budget_tier.value}",
        ],
        soft_preferences=[
            f"Pace: {request.pace}",
            f"Interests: {', '.join(request.interests) if request.interests else 'none provided'}",
            f"Accommodation preference: {request.accommodation_preference or 'not specified'}",
            f"Transport preference: {request.transport_preference or 'not specified'}",
        ],
        completion_definition="The coordinator has received specialist artifacts, review is satisfied, and governance has no blocking escalation.",
    )
    task_board = [
        AgentTask(
            task_id="clarify_request",
            title="Clarify missing trip inputs",
            owner_role=AgentRole.CLARIFICATION,
            goal="Determine whether user clarification is still required before autonomous planning continues.",
            deliverable_key="clarification_questions",
            allowed_delegate_roles=[],
            acceptance_criteria=[
                "Only blocking questions remain.",
                "Non-blocking preference gaps are recorded without stopping planning.",
            ],
            context_keys=["request"],
        ),
        AgentTask(
            task_id="research_destination",
            title="Research destination context",
            owner_role=AgentRole.DESTINATION_RESEARCH,
            goal="Gather weather, neighborhood, activity, cost, and risk signals for the destination.",
            deliverable_key="destination_research",
            depends_on=["clarify_request"],
            acceptance_criteria=[
                "Research includes sources and key assumptions.",
                "Confidence and open gaps are explicit.",
            ],
            context_keys=["request", "clarification_questions"],
        ),
        AgentTask(
            task_id="draft_itinerary",
            title="Draft itinerary",
            owner_role=AgentRole.ITINERARY,
            goal="Build a day-by-day itinerary grounded in the destination research artifact.",
            deliverable_key="itinerary_plan",
            depends_on=["research_destination"],
            allowed_delegate_roles=[AgentRole.DESTINATION_RESEARCH],
            acceptance_criteria=[
                "Daily plan matches trip length and pace.",
                "Activities stay within researched areas unless explicitly flagged.",
            ],
            context_keys=["request", "destination_research"],
        ),
        AgentTask(
            task_id="recommend_stay",
            title="Recommend stay options",
            owner_role=AgentRole.STAY,
            goal="Recommend accommodation areas and options that fit the itinerary.",
            deliverable_key="stay_recommendation_plan",
            depends_on=["draft_itinerary"],
            acceptance_criteria=[
                "Stay options align with itinerary areas.",
                "Price bands align with budget tier.",
            ],
            context_keys=["request", "itinerary_plan"],
        ),
        AgentTask(
            task_id="plan_transport",
            title="Plan local transport",
            owner_role=AgentRole.TRANSPORT,
            goal="Plan airport and intra-city transport for the itinerary.",
            deliverable_key="local_transport_plan",
            depends_on=["draft_itinerary"],
            acceptance_criteria=[
                "Critical legs include primary and backup mode.",
                "Transport notes mention duration or fare guidance.",
            ],
            context_keys=["request", "itinerary_plan"],
        ),
        AgentTask(
            task_id="recommend_food",
            title="Recommend food",
            owner_role=AgentRole.FOOD,
            goal="Attach meal guidance and signature dishes to the itinerary.",
            deliverable_key="food_recommendation_plan",
            depends_on=["draft_itinerary"],
            acceptance_criteria=[
                "Recommendations are area-aware.",
                "Dietary constraints are acknowledged.",
            ],
            context_keys=["request", "itinerary_plan"],
        ),
        AgentTask(
            task_id="audit_budget",
            title="Audit budget fit",
            owner_role=AgentRole.BUDGET,
            goal="Estimate total spend and trigger revision if the plan is materially over budget.",
            deliverable_key="budget_assessment",
            depends_on=["draft_itinerary", "recommend_stay", "plan_transport", "recommend_food"],
            allowed_delegate_roles=[AgentRole.ITINERARY, AgentRole.STAY, AgentRole.TRANSPORT, AgentRole.FOOD],
            acceptance_criteria=[
                "Estimated total cost is explicit.",
                "Optimization actions are concrete.",
            ],
            context_keys=[
                "request",
                "itinerary_plan",
                "stay_recommendation_plan",
                "local_transport_plan",
                "food_recommendation_plan",
            ],
        ),
        AgentTask(
            task_id="review_safety",
            title="Review safety posture",
            owner_role=AgentRole.SAFETY,
            goal="Assess situational safety considerations for the itinerary.",
            deliverable_key="solo_women_safety_assessment",
            depends_on=["draft_itinerary"],
            acceptance_criteria=[
                "Risk signals are explicit.",
                "Mitigations are actionable.",
            ],
            context_keys=["request", "itinerary_plan"],
        ),
        AgentTask(
            task_id="critique_plan",
            title="Critique final plan",
            owner_role=AgentRole.REVIEW,
            goal="Review the full plan for coherence, confidence, and unsupported claims.",
            deliverable_key="review_assessment",
            depends_on=["audit_budget", "review_safety"],
            allowed_delegate_roles=[
                AgentRole.ITINERARY,
                AgentRole.STAY,
                AgentRole.TRANSPORT,
                AgentRole.FOOD,
                AgentRole.BUDGET,
                AgentRole.SAFETY,
            ],
            acceptance_criteria=[
                "Review identifies concrete issues, not generic criticism.",
                "Revision requests are targeted to the right specialist.",
            ],
            context_keys=[
                "request",
                "destination_research",
                "itinerary_plan",
                "stay_recommendation_plan",
                "local_transport_plan",
                "food_recommendation_plan",
                "budget_assessment",
                "solo_women_safety_assessment",
            ],
        ),
        AgentTask(
            task_id="govern_plan",
            title="Apply governance gate",
            owner_role=AgentRole.GOVERNANCE,
            goal="Apply policy, confidence, and escalation checks before completion.",
            deliverable_key="governance_decision",
            depends_on=["critique_plan"],
            acceptance_criteria=[
                "Blocking governance flags are explicit.",
                "Escalation path is clear when approval is not automatic.",
            ],
            context_keys=["review_assessment", "budget_assessment"],
        ),
    ]
    return CoordinationLedger(objective=objective, task_board=task_board)
