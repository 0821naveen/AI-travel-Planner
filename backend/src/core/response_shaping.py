from __future__ import annotations

from src.agents.travel_planner.schemas import CreateTripResponse


def shape_trip_response(response: CreateTripResponse) -> CreateTripResponse:
    shaped = CreateTripResponse.model_validate(response.model_dump(mode="json"))
    if shaped.destination_research is not None:
        shaped.destination_research.sources = shaped.destination_research.sources[:8]
        for source in shaped.destination_research.sources:
            source.snippet = source.snippet[:600]
    if shaped.review_assessment is not None:
        shaped.review_assessment.final_notes = shaped.review_assessment.final_notes[:10]
        shaped.review_assessment.issues = shaped.review_assessment.issues[:10]
    return shaped
