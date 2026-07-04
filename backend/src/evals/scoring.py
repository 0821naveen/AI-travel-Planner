from __future__ import annotations

from dataclasses import dataclass

from src.agents.travel_planner.state import PlannerContext


@dataclass(frozen=True)
class EvalScores:
    research_usefulness: float
    itinerary_quality: float
    budget_realism: float
    safety_guidance: float
    overall: float


def _bounded(score: float) -> float:
    return max(0.0, min(1.0, round(score, 4)))


def score_research_usefulness(context: PlannerContext) -> float:
    report = context.destination_research
    if report is None:
        return 0.0
    score = 0.0
    if report.summary:
        score += 0.2
    if report.recommended_areas:
        score += 0.2
    if report.top_highlights:
        score += 0.15
    if report.planning_tips:
        score += 0.15
    if report.sources:
        score += 0.15
    score += 0.15 * report.confidence
    return _bounded(score)


def score_itinerary_quality(context: PlannerContext) -> float:
    itinerary = context.itinerary_plan
    if itinerary is None:
        return 0.0
    expected_days = int(context.research_signals.get("days", len(itinerary.days) or 1))
    score = 0.0
    if itinerary.summary:
        score += 0.15
    if len(itinerary.days) == expected_days:
        score += 0.3
    if itinerary.days and all(day.area for day in itinerary.days):
        score += 0.2
    if itinerary.budget_fit_note:
        score += 0.15
    if itinerary.days and all(day.reasoning for day in itinerary.days):
        score += 0.1
    score += 0.1 * itinerary.confidence
    return _bounded(score)


def score_budget_realism(context: PlannerContext) -> float:
    assessment = context.budget_assessment
    if assessment is None:
        return 0.0
    score = 0.0
    if assessment.summary:
        score += 0.2
    if assessment.estimated_total_cost:
        score += 0.2
    if assessment.cost_drivers:
        score += 0.2
    if assessment.optimization_actions:
        score += 0.15
    if context.status.value in {"budget_warning", "ready_for_review", "completed"}:
        score += 0.1
    score += 0.15 * assessment.confidence
    return _bounded(score)


def score_safety_guidance(context: PlannerContext) -> float:
    assessment = context.solo_women_safety_assessment
    if assessment is None:
        return 0.0
    score = 0.0
    if assessment.summary:
        score += 0.2
    if assessment.night_transport_guidance:
        score += 0.2
    if assessment.lodging_safety_tips:
        score += 0.2
    if assessment.safe_areas or assessment.caution_areas:
        score += 0.15
    if assessment.itinerary_adjustments:
        score += 0.1
    score += 0.15 * assessment.confidence
    return _bounded(score)


def score_context(context: PlannerContext) -> EvalScores:
    research = score_research_usefulness(context)
    itinerary = score_itinerary_quality(context)
    budget = score_budget_realism(context)
    safety = score_safety_guidance(context)
    overall = _bounded((research + itinerary + budget + safety) / 4)
    return EvalScores(
        research_usefulness=research,
        itinerary_quality=itinerary,
        budget_realism=budget,
        safety_guidance=safety,
        overall=overall,
    )
