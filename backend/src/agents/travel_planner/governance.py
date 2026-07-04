from __future__ import annotations

from dataclasses import dataclass

from src.agents.travel_planner.state import PlannerContext

LOW_CONFIDENCE_THRESHOLD = 0.45
EARLY_EXIT_THRESHOLD = 0.3


@dataclass(frozen=True)
class GovernanceDecision:
    flags: list[str]
    approve: bool


def evaluate_governance(context: PlannerContext) -> GovernanceDecision:
    flags: list[str] = []

    destination_confidence = context.destination_research.confidence if context.destination_research else 0.0
    itinerary_confidence = context.itinerary_plan.confidence if context.itinerary_plan else 0.0
    stay_confidence = context.stay_recommendation_plan.confidence if context.stay_recommendation_plan else 0.0
    transport_confidence = context.local_transport_plan.confidence if context.local_transport_plan else 0.0
    food_confidence = context.food_recommendation_plan.confidence if context.food_recommendation_plan else 0.0
    budget_confidence = context.budget_assessment.confidence if context.budget_assessment else 0.0
    safety_confidence = (
        context.solo_women_safety_assessment.confidence if context.solo_women_safety_assessment else 0.0
    )
    review_confidence = context.review_assessment.confidence if context.review_assessment else 0.0

    for label, score in {
        "destination_research": destination_confidence,
        "itinerary_plan": itinerary_confidence,
        "stay_recommendation": stay_confidence,
        "local_transport": transport_confidence,
        "food_recommendation": food_confidence,
        "budget_assessment": budget_confidence,
        "safety_assessment": safety_confidence,
        "review_assessment": review_confidence,
    }.items():
        if 0.0 < score < LOW_CONFIDENCE_THRESHOLD:
            flags.append(f"low_confidence:{label}")

    if context.budget_assessment and not context.budget_assessment.within_budget:
        flags.append("budget_exceeds_target")

    if context.review_assessment and context.review_assessment.issues:
        flags.append("review_reported_issues")

    if context.destination_research and context.itinerary_plan:
        research_areas = set(area.lower() for area in context.destination_research.recommended_areas)
        itinerary_areas = set(day.area.lower() for day in context.itinerary_plan.days if day.area)
        if research_areas and itinerary_areas and itinerary_areas.isdisjoint(research_areas):
            flags.append("itinerary_outside_researched_areas")

    approve = not flags
    return GovernanceDecision(flags=flags, approve=approve)


def should_route_early_to_review(step_name: str, context: PlannerContext) -> bool:
    # Always let the workflow build itinerary and downstream planning artifacts.
    # Low-confidence research should still result in a draft itinerary and budget
    # instead of short-circuiting the UI into empty tabs.
    if step_name == "budget_optimization_agent" and context.budget_assessment:
        return (
            context.budget_assessment.confidence < EARLY_EXIT_THRESHOLD
            or not context.budget_assessment.within_budget
        )
    if step_name == "solo_women_safety_advisor_agent" and context.solo_women_safety_assessment:
        return context.solo_women_safety_assessment.confidence < EARLY_EXIT_THRESHOLD
    return False
