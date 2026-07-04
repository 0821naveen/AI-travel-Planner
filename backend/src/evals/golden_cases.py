from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.agents.travel_planner.schemas import BudgetTier, TravelerConstraints, TripPurpose, TripRequest


@dataclass(frozen=True)
class EvalExpectation:
    min_scores: dict[str, float] = field(default_factory=dict)
    required_flags: list[str] = field(default_factory=list)
    forbidden_flags: list[str] = field(default_factory=list)
    expected_status: str | None = None
    expected_route_contains: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    kind: str
    request: TripRequest
    web_search_summary: str
    weather_payload: dict[str, Any]
    agent_outputs: dict[str, dict[str, Any]]
    failing_tools: dict[str, str] = field(default_factory=dict)
    failing_agents: dict[str, str] = field(default_factory=dict)
    expectation: EvalExpectation = field(default_factory=EvalExpectation)


def _build_success_case() -> EvalCase:
    return EvalCase(
        case_id="city_leisure_success",
        kind="golden",
        request=TripRequest(
            origin_city="Bengaluru",
            destination="Kyoto",
            start_date="2099-04-10",
            end_date="2099-04-12",
            traveler_count=2,
            trip_purpose=TripPurpose.LEISURE,
            total_budget=45000,
            budget_tier=BudgetTier.MID_RANGE,
            pace="balanced",
            interests=["food", "temples", "walks"],
            accommodation_preference="boutique hotel",
            transport_preference="public transit",
            constraints=TravelerConstraints(notes="No special constraints."),
        ),
        web_search_summary="Kyoto research points to Gion, Higashiyama, and Arashiyama as strong visitor areas.",
        weather_payload={
            "location": {"name": "Kyoto"},
            "current": {"temp_c": 22, "condition": {"text": "Clear"}},
        },
        agent_outputs={
            "destination_research_agent": {
                "summary": "Kyoto is a strong fit for a balanced leisure trip focused on food, temple districts, and walkable neighborhoods.",
                "interest_fit": ["Traditional food culture", "Temple visits", "Walkable historic streets"],
                "recommended_areas": ["Gion", "Higashiyama", "Arashiyama"],
                "local_transport_notes": ["Use trains for district jumps and buses for last-mile access."],
                "top_highlights": ["Historic districts", "Food markets", "Early-morning temple visits"],
                "top_risks": ["Popular sites get crowded later in the day"],
                "planning_tips": ["Start sightseeing early", "Cluster activities by district"],
                "hotel_price_signal": "Mid-range hotels trend moderate to high in central districts.",
                "flight_price_signal": "International airfare is variable and should be booked early.",
                "assumptions": ["Public transit is acceptable for most movements."],
                "confidence": 0.88,
            },
            "itinerary_planning_agent": {
                "summary": "A three-day Kyoto plan that groups activities by district and keeps arrival and departure days lighter.",
                "days": [
                    {
                        "day_number": 1,
                        "date": "2099-04-10",
                        "theme": "Gion orientation",
                        "morning": "Arrival and check-in",
                        "afternoon": "Walk through Gion and nearby lanes",
                        "evening": "Relaxed dinner in Gion",
                        "area": "Gion",
                        "transport_note": "Use direct public transit from arrival point.",
                        "pace_level": "balanced",
                        "estimated_daily_cost": "Approximately 15000 total per day",
                        "reasoning": "Keeps arrival day light and area-focused.",
                        "warnings": [],
                    },
                    {
                        "day_number": 2,
                        "date": "2099-04-11",
                        "theme": "Higashiyama temple circuit",
                        "morning": "Temple visits and neighborhood walk",
                        "afternoon": "Food-focused stop and cultural exploration",
                        "evening": "Scenic evening walk",
                        "area": "Higashiyama",
                        "transport_note": "Short transit hops with walking between sites.",
                        "pace_level": "balanced",
                        "estimated_daily_cost": "Approximately 15000 total per day",
                        "reasoning": "Clusters core interests into one historic district.",
                        "warnings": [],
                    },
                    {
                        "day_number": 3,
                        "date": "2099-04-12",
                        "theme": "Arashiyama wrap-up",
                        "morning": "Early district exploration",
                        "afternoon": "Flexible lunch and departure preparation",
                        "evening": "Departure",
                        "area": "Arashiyama",
                        "transport_note": "Use direct rail connection where possible.",
                        "pace_level": "balanced",
                        "estimated_daily_cost": "Approximately 15000 total per day",
                        "reasoning": "Creates a lighter departure day without overpacking.",
                        "warnings": [],
                    },
                ],
                "budget_fit_note": "The itinerary stays within the target when districts are grouped tightly.",
                "assumptions": ["Arrival timing allows a partial first-day walk."],
                "confidence": 0.9,
            },
            "stay_recommendation_agent": {
                "summary": "Stay near Gion or Higashiyama for the strongest district fit.",
                "recommendations": [
                    {
                        "name": "Gion stay cluster",
                        "stay_type": "boutique hotel",
                        "area": "Gion",
                        "price_band": "mid_range",
                        "why_fit": "Central to the first two days and strong for evening walkability.",
                        "safety_notes": ["Stay on active streets with clear transit access."],
                        "booking_tips": ["Book early for peak season weekends."],
                    }
                ],
                "confidence": 0.82,
            },
            "local_transport_agent": {
                "summary": "Public transit plus short walking segments is the most realistic pattern.",
                "legs": [
                    {
                        "day_number": 1,
                        "from_area": "Station area",
                        "to_area": "Gion",
                        "recommended_mode": "train",
                        "backup_mode": "taxi",
                        "approx_duration": "25 minutes",
                        "approx_fare": "Low to moderate local fare",
                        "notes": "Move directly to the stay area before starting local exploration.",
                    }
                ],
                "confidence": 0.8,
            },
            "food_recommendation_agent": {
                "summary": "Food recommendations are aligned to temple districts and evening walk areas.",
                "recommendations": [
                    {
                        "day_number": 1,
                        "meal": "dinner",
                        "venue_name": "Gion local dining lane",
                        "area": "Gion",
                        "cuisine_type": "Kyoto specialties",
                        "price_level": "mid_range",
                        "dietary_fit": "General fit",
                        "why_fit": "Close to the first-day walking area.",
                    },
                    {
                        "day_number": 2,
                        "meal": "lunch",
                        "venue_name": "Higashiyama casual set-menu stop",
                        "area": "Higashiyama",
                        "cuisine_type": "Local set meals",
                        "price_level": "mid_range",
                        "dietary_fit": "General fit",
                        "why_fit": "Works well in the middle of the district route.",
                    },
                ],
                "confidence": 0.83,
            },
            "budget_optimization_agent": {
                "within_budget": True,
                "estimated_total_cost": "Approximately 38000 to 42000 total",
                "estimated_daily_cost": "Approximately 13000 to 15000 total per day",
                "summary": "The grouped district plan is realistic for the stated budget tier.",
                "cost_drivers": ["Accommodation", "Intercity arrival cost"],
                "optimization_actions": ["Keep dinners in the mid-range band", "Use rail over taxis for district moves"],
                "warnings": [],
                "confidence": 0.79,
            },
            "solo_women_safety_advisor_agent": {
                "applies": False,
                "summary": "General safety guidance is sufficient for this two-traveler trip.",
                "solo_traveler_fit": "general guidance",
                "women_safety_risk_level": "moderate",
                "safe_areas": ["Gion", "Higashiyama"],
                "caution_areas": [],
                "night_transport_guidance": ["Use direct registered transport after late dinners."],
                "lodging_safety_tips": ["Choose well-reviewed lodging near active streets."],
                "solo_friendly_suggestions": [],
                "itinerary_adjustments": [],
                "confidence": 0.72,
            },
            "review_and_consistency_agent": {
                "approved": True,
                "summary": "Research, itinerary, and budget are coherent and practical together.",
                "consistency_score": 0.91,
                "strengths": ["Areas are consistent across steps", "Budget is plausible"],
                "issues": [],
                "recommended_fixes": [],
                "final_notes": ["Ready to share with the traveler."],
                "confidence": 0.86,
            },
        },
        expectation=EvalExpectation(
            min_scores={
                "research_usefulness": 0.8,
                "itinerary_quality": 0.85,
                "budget_realism": 0.75,
                "safety_guidance": 0.65,
                "overall": 0.78,
            },
            forbidden_flags=["itinerary_outside_researched_areas", "budget_exceeds_target"],
            expected_status="completed",
            expected_route_contains=["governance_gate_agent"],
        ),
    )


def _build_failure_cases() -> list[EvalCase]:
    base_request = TripRequest(
        origin_city="Mumbai",
        destination="Jaipur",
        start_date="2099-09-14",
        end_date="2099-09-16",
        traveler_count=1,
        trip_purpose=TripPurpose.LEISURE,
        total_budget=15000,
        budget_tier=BudgetTier.BUDGET,
        pace="balanced",
        interests=["markets", "food", "history"],
        accommodation_preference="guesthouse",
        transport_preference="public transit",
        constraints=TravelerConstraints(notes="Solo traveler"),
    )
    common_outputs = {
        "destination_research_agent": {
            "summary": "Jaipur has strong history and food fit but needs area-aware planning.",
            "interest_fit": ["Markets", "History", "Local food"],
            "recommended_areas": ["Pink City"],
            "local_transport_notes": ["Use trusted ride-hailing at night."],
            "top_highlights": ["Historic core", "Food lanes"],
            "top_risks": ["Traffic and crowding later in the day"],
            "planning_tips": ["Start early", "Stay close to the core district"],
            "hotel_price_signal": "Budget stays available with review discipline.",
            "flight_price_signal": "Variable domestic pricing.",
            "assumptions": ["Short city break with light luggage."],
            "confidence": 0.81,
        },
        "itinerary_planning_agent": {
            "summary": "A compact Jaipur plan centered on the historic core.",
            "days": [
                {
                    "day_number": 1,
                    "date": "2099-09-14",
                    "theme": "Old city orientation",
                    "morning": "Arrival and check-in",
                    "afternoon": "Walk through the historic core",
                    "evening": "Early dinner near the stay area",
                    "area": "Pink City",
                    "transport_note": "Short direct transfers only.",
                    "pace_level": "balanced",
                    "estimated_daily_cost": "Approximately 5000 total per day",
                    "reasoning": "Keeps the first day compact and realistic.",
                    "warnings": [],
                },
                {
                    "day_number": 2,
                    "date": "2099-09-15",
                    "theme": "History and food day",
                    "morning": "Historic site visit",
                    "afternoon": "Market and lunch block",
                    "evening": "Return before late night",
                    "area": "Pink City",
                    "transport_note": "Use direct transport after dark.",
                    "pace_level": "balanced",
                    "estimated_daily_cost": "Approximately 5000 total per day",
                    "reasoning": "Keeps movements tight for safety and budget.",
                    "warnings": [],
                },
                {
                    "day_number": 3,
                    "date": "2099-09-16",
                    "theme": "Wrap-up and departure",
                    "morning": "Flexible final walk",
                    "afternoon": "Departure prep",
                    "evening": "Departure",
                    "area": "Pink City",
                    "transport_note": "Use the simplest departure route.",
                    "pace_level": "balanced",
                    "estimated_daily_cost": "Approximately 5000 total per day",
                    "reasoning": "Departure day kept intentionally light.",
                    "warnings": [],
                },
            ],
            "budget_fit_note": "District clustering is important to stay within budget.",
            "assumptions": [],
            "confidence": 0.82,
        },
        "stay_recommendation_agent": {
            "summary": "Stay recommendations favor the historic core.",
            "recommendations": [
                {
                    "name": "Pink City guesthouse cluster",
                    "stay_type": "guesthouse",
                    "area": "Pink City",
                    "price_band": "budget",
                    "why_fit": "Reduces night movement complexity.",
                    "safety_notes": ["Choose an active street with recent reviews."],
                    "booking_tips": ["Confirm late arrival handling."],
                }
            ],
            "confidence": 0.76,
        },
        "local_transport_agent": {
            "summary": "Direct rides and short walks are the safest pattern for this solo trip.",
            "legs": [
                {
                    "day_number": 1,
                    "from_area": "Arrival point",
                    "to_area": "Pink City",
                    "recommended_mode": "registered taxi",
                    "backup_mode": "ride-hailing",
                    "approx_duration": "20 minutes",
                    "approx_fare": "Low to moderate fare",
                    "notes": "Avoid unnecessary late-night transfers.",
                }
            ],
            "confidence": 0.78,
        },
        "food_recommendation_agent": {
            "summary": "Food suggestions stay inside the historic core to reduce movement.",
            "recommendations": [
                {
                    "day_number": 1,
                    "meal": "dinner",
                    "venue_name": "Pink City local restaurant lane",
                    "area": "Pink City",
                    "cuisine_type": "Rajasthani specialties",
                    "price_level": "budget",
                    "dietary_fit": "General fit",
                    "why_fit": "Minimizes travel after dark.",
                }
            ],
            "confidence": 0.77,
        },
        "budget_optimization_agent": {
            "within_budget": True,
            "estimated_total_cost": "Approximately 13000 to 14500 total",
            "estimated_daily_cost": "Approximately 4300 to 4800 total per day",
            "summary": "The plan is tight but plausible if transport is kept direct.",
            "cost_drivers": ["Arrival transfer", "Lodging"],
            "optimization_actions": ["Keep meals in the budget band", "Avoid fragmented transport patterns"],
            "warnings": [],
            "confidence": 0.73,
        },
        "solo_women_safety_advisor_agent": {
            "applies": True,
            "summary": "This trip needs practical night-movement discipline and central lodging.",
            "solo_traveler_fit": "good with precautions",
            "women_safety_risk_level": "moderate",
            "safe_areas": ["Pink City"],
            "caution_areas": ["Low-traffic peripheral streets at night"],
            "night_transport_guidance": ["Use direct registered transport after dark."],
            "lodging_safety_tips": ["Choose properties with strong recent reviews."],
            "solo_friendly_suggestions": ["Keep evening plans close to the stay area."],
            "itinerary_adjustments": ["Return earlier on food-focused evenings."],
            "confidence": 0.8,
        },
        "review_and_consistency_agent": {
            "approved": True,
            "summary": "The solo itinerary is coherent when safety constraints are respected.",
            "consistency_score": 0.82,
            "strengths": ["Strong area clustering", "Budget is plausible"],
            "issues": [],
            "recommended_fixes": [],
            "final_notes": ["Ready with the stated precautions."],
            "confidence": 0.79,
        },
    }
    return [
        EvalCase(
            case_id="invalid_json_fallback",
            kind="failure",
            request=base_request,
            web_search_summary="Core research is available but synthesis fails.",
            weather_payload={"location": {"name": "Jaipur"}, "current": {"temp_c": 31, "condition": {"text": "Sunny"}}},
            agent_outputs=common_outputs,
            failing_agents={"destination_research_agent": "invalid_json"},
            expectation=EvalExpectation(
                required_flags=["low_confidence:destination_research"],
                expected_status="ready_for_review",
                expected_route_contains=["review_and_consistency_agent"],
            ),
        ),
        EvalCase(
            case_id="tool_timeout_fallback",
            kind="failure",
            request=base_request,
            web_search_summary="Web search times out but the run should degrade safely.",
            weather_payload={"location": {"name": "Jaipur"}, "current": {"temp_c": 31, "condition": {"text": "Sunny"}}},
            agent_outputs=common_outputs,
            failing_tools={"web_search": "timeout"},
            expectation=EvalExpectation(
                expected_status="completed",
                expected_route_contains=["governance_gate_agent"],
            ),
        ),
        EvalCase(
            case_id="contradictory_sources_review",
            kind="failure",
            request=base_request,
            web_search_summary="Research and itinerary intentionally disagree to test governance.",
            weather_payload={"location": {"name": "Jaipur"}, "current": {"temp_c": 31, "condition": {"text": "Sunny"}}},
            agent_outputs={
                **common_outputs,
                "destination_research_agent": {
                    **common_outputs["destination_research_agent"],
                    "recommended_areas": ["North District"],
                },
                "itinerary_planning_agent": {
                    **common_outputs["itinerary_planning_agent"],
                    "days": [
                        {
                            **common_outputs["itinerary_planning_agent"]["days"][0],
                            "area": "South District",
                        },
                        {
                            **common_outputs["itinerary_planning_agent"]["days"][1],
                            "area": "South District",
                        },
                        {
                            **common_outputs["itinerary_planning_agent"]["days"][2],
                            "area": "South District",
                        },
                    ],
                },
                "review_and_consistency_agent": {
                    **common_outputs["review_and_consistency_agent"],
                    "approved": False,
                    "issues": ["Itinerary areas do not match researched neighborhood guidance."],
                    "recommended_fixes": ["Realign the day plan to researched districts."],
                },
            },
            expectation=EvalExpectation(
                required_flags=["itinerary_outside_researched_areas", "review_reported_issues"],
                expected_status="ready_for_review",
                expected_route_contains=["governance_gate_agent"],
            ),
        ),
    ]


GOLDEN_CASES: list[EvalCase] = [_build_success_case()]
FAILURE_CASES: list[EvalCase] = _build_failure_cases()
