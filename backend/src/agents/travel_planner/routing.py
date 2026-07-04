from __future__ import annotations

from src.agents.travel_planner.state import PlannerContext
from src.domain.trips.policies import ClarificationPolicy


def route_after_clarification(context: PlannerContext):
    return ClarificationPolicy().status_for(context.clarification_questions)
