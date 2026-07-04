from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from src.agents.travel_planner.schemas import TripRequest
from src.agents.travel_planner.tools import trip_days


@dataclass(frozen=True)
class TripResearchSignalService:
    def build(self, request: TripRequest) -> Dict[str, Any]:
        days = trip_days(request.start_date, request.end_date)
        budget_per_day = round(request.total_budget / max(1, days), 2)
        return {
            "days": days,
            "budget_per_day": budget_per_day,
            "budget_tier": request.budget_tier.value,
            "traveler_count": request.traveler_count,
            "trip_purpose": request.trip_purpose.value,
        }
