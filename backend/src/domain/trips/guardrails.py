from __future__ import annotations

from src.agents.travel_planner.schemas import ReviewAssessment, TripStatus
from src.agents.travel_planner.state import PlannerContext

UNSAFE_PATTERNS = (
    "ignore local laws",
    "carry large amounts of cash",
    "walk alone late at night",
    "share personal documents freely",
)


def apply_trip_guardrails(context: PlannerContext) -> PlannerContext:
    issues: list[str] = []

    if context.destination_research and context.itinerary_plan:
        researched = {item.lower() for item in context.destination_research.recommended_areas}
        planned = {day.area.lower() for day in context.itinerary_plan.days if day.area}
        if researched and planned and planned.isdisjoint(researched):
            issues.append("Itinerary areas are not grounded in researched destination areas.")

    if context.budget_assessment and not context.budget_assessment.within_budget:
        issues.append("The proposed trip plan exceeds the traveler budget.")

    if context.solo_women_safety_assessment and context.solo_women_safety_assessment.women_safety_risk_level.lower() in {
        "high",
        "severe",
    }:
        issues.append("Safety assessment indicates elevated risk requiring manual review.")

    text_blobs = [
        context.destination_research.summary if context.destination_research else "",
        context.itinerary_plan.summary if context.itinerary_plan else "",
        context.review_assessment.summary if context.review_assessment else "",
    ]
    combined = " ".join(text_blobs).lower()
    for pattern in UNSAFE_PATTERNS:
        if pattern in combined:
            issues.append(f"Unsafe travel guidance detected: '{pattern}'.")

    if issues:
        review = context.review_assessment or ReviewAssessment(
            destination=context.request.destination,
            approved=False,
            summary="Guardrail review blocked automatic approval.",
        )
        review.approved = False
        review.issues = list(dict.fromkeys([*review.issues, *issues]))
        review.recommended_fixes = list(
            dict.fromkeys(
                [
                    *review.recommended_fixes,
                    "Review unsafe or unsupported recommendations before finalizing the plan.",
                ]
            )
        )
        context.review_assessment = review
        context.status = TripStatus.READY_FOR_REVIEW
    return context
