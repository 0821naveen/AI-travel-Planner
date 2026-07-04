from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Type

from pydantic import BaseModel, Field

from src.agents.travel_planner.schemas import (
    BudgetAssessment,
    ClarificationQuestion,
    DestinationResearchReport,
    FoodRecommendationPlan,
    ItineraryPlan,
    LocalTransportPlan,
    ReviewAssessment,
    SoloWomenSafetyAssessment,
    StayRecommendationPlan,
    TripRequest,
    TripStatus,
)
from src.agents.travel_planner.state import PlannerContext


class AgentContractBase(BaseModel):
    fallback_used: bool = False
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ClarificationInput(AgentContractBase):
    request: TripRequest


class ClarificationOutput(AgentContractBase):
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list)
    status: TripStatus


class ResearchSignalInput(AgentContractBase):
    request: TripRequest


class ResearchSignalOutput(AgentContractBase):
    research_signals: dict[str, object] = Field(default_factory=dict)


class DestinationResearchInput(AgentContractBase):
    request: TripRequest
    research_signals: dict[str, object] = Field(default_factory=dict)


class DestinationResearchOutput(AgentContractBase):
    destination_research: DestinationResearchReport


class ItineraryPlanningInput(AgentContractBase):
    request: TripRequest
    destination_research: Optional[DestinationResearchReport] = None
    research_signals: dict[str, object] = Field(default_factory=dict)


class ItineraryPlanningOutput(AgentContractBase):
    itinerary_plan: ItineraryPlan


class StayRecommendationInput(AgentContractBase):
    request: TripRequest
    itinerary_plan: Optional[ItineraryPlan] = None


class StayRecommendationOutput(AgentContractBase):
    stay_recommendation_plan: StayRecommendationPlan


class LocalTransportInput(AgentContractBase):
    request: TripRequest
    itinerary_plan: Optional[ItineraryPlan] = None


class LocalTransportOutput(AgentContractBase):
    local_transport_plan: LocalTransportPlan


class FoodRecommendationInput(AgentContractBase):
    request: TripRequest
    itinerary_plan: Optional[ItineraryPlan] = None


class FoodRecommendationOutput(AgentContractBase):
    food_recommendation_plan: FoodRecommendationPlan


class BudgetOptimizationInput(AgentContractBase):
    request: TripRequest
    itinerary_plan: Optional[ItineraryPlan] = None


class BudgetOptimizationOutput(AgentContractBase):
    budget_assessment: BudgetAssessment


class SafetyAdvisorInput(AgentContractBase):
    request: TripRequest
    itinerary_plan: Optional[ItineraryPlan] = None


class SafetyAdvisorOutput(AgentContractBase):
    solo_women_safety_assessment: SoloWomenSafetyAssessment


class ReviewInput(AgentContractBase):
    request: TripRequest
    itinerary_plan: Optional[ItineraryPlan] = None


class ReviewOutput(AgentContractBase):
    review_assessment: ReviewAssessment


class GovernanceInput(AgentContractBase):
    request: TripRequest
    review_assessment: ReviewAssessment
    governance_flags: list[str] = Field(default_factory=list)


class GovernanceOutput(AgentContractBase):
    review_assessment: ReviewAssessment
    governance_flags: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    responsibility: str
    input_model: Type[BaseModel]
    output_model: Type[BaseModel]
    allowed_tools: tuple[str, ...]
    build_input: Callable[[PlannerContext], BaseModel]
    build_output: Callable[[PlannerContext], BaseModel]


def _fallback_used(confidence: float) -> bool:
    return confidence < 0.5


def build_agent_definitions() -> dict[str, AgentDefinition]:
    return {
        "clarification_validator": AgentDefinition(
            name="clarification_validator",
            responsibility="Validate whether the trip request needs clarification before research begins.",
            input_model=ClarificationInput,
            output_model=ClarificationOutput,
            allowed_tools=(),
            build_input=lambda context: ClarificationInput(request=context.request),
            build_output=lambda context: ClarificationOutput(
                clarification_questions=context.clarification_questions,
                status=context.status,
                confidence=1.0,
                fallback_used=False,
            ),
        ),
        "research_signal_agent": AgentDefinition(
            name="research_signal_agent",
            responsibility="Derive deterministic trip research signals from the user request.",
            input_model=ResearchSignalInput,
            output_model=ResearchSignalOutput,
            allowed_tools=(),
            build_input=lambda context: ResearchSignalInput(request=context.request),
            build_output=lambda context: ResearchSignalOutput(research_signals=context.research_signals, confidence=1.0),
        ),
        "destination_research_agent": AgentDefinition(
            name="destination_research_agent",
            responsibility="Assemble researched destination context, risks, and planning signals.",
            input_model=DestinationResearchInput,
            output_model=DestinationResearchOutput,
            allowed_tools=("weather_lookup", "web_search", "google_flights_search", "flight_schedule_lookup", "json_completion"),
            build_input=lambda context: DestinationResearchInput(
                request=context.request,
                research_signals=context.research_signals,
            ),
            build_output=lambda context: DestinationResearchOutput(
                destination_research=context.destination_research,
                confidence=context.destination_research.confidence if context.destination_research else 0.0,
                fallback_used=_fallback_used(context.destination_research.confidence if context.destination_research else 0.0),
            ),
        ),
        "itinerary_planning_agent": AgentDefinition(
            name="itinerary_planning_agent",
            responsibility="Produce the day-by-day itinerary plan from researched destination context.",
            input_model=ItineraryPlanningInput,
            output_model=ItineraryPlanningOutput,
            allowed_tools=("web_search", "json_completion"),
            build_input=lambda context: ItineraryPlanningInput(
                request=context.request,
                destination_research=context.destination_research,
                research_signals=context.research_signals,
            ),
            build_output=lambda context: ItineraryPlanningOutput(
                itinerary_plan=context.itinerary_plan,
                confidence=context.itinerary_plan.confidence if context.itinerary_plan else 0.0,
                fallback_used=_fallback_used(context.itinerary_plan.confidence if context.itinerary_plan else 0.0),
            ),
        ),
        "stay_recommendation_agent": AgentDefinition(
            name="stay_recommendation_agent",
            responsibility="Recommend stay options constrained to itinerary and neighborhood fit.",
            input_model=StayRecommendationInput,
            output_model=StayRecommendationOutput,
            allowed_tools=("web_search", "google_hotels_search", "json_completion"),
            build_input=lambda context: StayRecommendationInput(
                request=context.request,
                itinerary_plan=context.itinerary_plan,
            ),
            build_output=lambda context: StayRecommendationOutput(
                stay_recommendation_plan=context.stay_recommendation_plan,
                confidence=context.stay_recommendation_plan.confidence if context.stay_recommendation_plan else 0.0,
                fallback_used=_fallback_used(
                    context.stay_recommendation_plan.confidence if context.stay_recommendation_plan else 0.0
                ),
            ),
        ),
        "local_transport_agent": AgentDefinition(
            name="local_transport_agent",
            responsibility="Recommend intra-city transport patterns for the planned itinerary.",
            input_model=LocalTransportInput,
            output_model=LocalTransportOutput,
            allowed_tools=("web_search", "json_completion"),
            build_input=lambda context: LocalTransportInput(
                request=context.request,
                itinerary_plan=context.itinerary_plan,
            ),
            build_output=lambda context: LocalTransportOutput(
                local_transport_plan=context.local_transport_plan,
                confidence=context.local_transport_plan.confidence if context.local_transport_plan else 0.0,
                fallback_used=_fallback_used(
                    context.local_transport_plan.confidence if context.local_transport_plan else 0.0
                ),
            ),
        ),
        "food_recommendation_agent": AgentDefinition(
            name="food_recommendation_agent",
            responsibility="Recommend food choices that fit itinerary area, budget, and traveler constraints.",
            input_model=FoodRecommendationInput,
            output_model=FoodRecommendationOutput,
            allowed_tools=("web_search", "youtube_video_details", "json_completion"),
            build_input=lambda context: FoodRecommendationInput(
                request=context.request,
                itinerary_plan=context.itinerary_plan,
            ),
            build_output=lambda context: FoodRecommendationOutput(
                food_recommendation_plan=context.food_recommendation_plan,
                confidence=context.food_recommendation_plan.confidence if context.food_recommendation_plan else 0.0,
                fallback_used=_fallback_used(
                    context.food_recommendation_plan.confidence if context.food_recommendation_plan else 0.0
                ),
            ),
        ),
        "budget_optimization_agent": AgentDefinition(
            name="budget_optimization_agent",
            responsibility="Assess budget fit and propose optimization actions.",
            input_model=BudgetOptimizationInput,
            output_model=BudgetOptimizationOutput,
            allowed_tools=("json_completion",),
            build_input=lambda context: BudgetOptimizationInput(
                request=context.request,
                itinerary_plan=context.itinerary_plan,
            ),
            build_output=lambda context: BudgetOptimizationOutput(
                budget_assessment=context.budget_assessment,
                confidence=context.budget_assessment.confidence if context.budget_assessment else 0.0,
                fallback_used=_fallback_used(context.budget_assessment.confidence if context.budget_assessment else 0.0),
            ),
        ),
        "solo_women_safety_advisor_agent": AgentDefinition(
            name="solo_women_safety_advisor_agent",
            responsibility="Assess solo and women-focused travel safety concerns for the itinerary.",
            input_model=SafetyAdvisorInput,
            output_model=SafetyAdvisorOutput,
            allowed_tools=("json_completion",),
            build_input=lambda context: SafetyAdvisorInput(
                request=context.request,
                itinerary_plan=context.itinerary_plan,
            ),
            build_output=lambda context: SafetyAdvisorOutput(
                solo_women_safety_assessment=context.solo_women_safety_assessment,
                confidence=context.solo_women_safety_assessment.confidence
                if context.solo_women_safety_assessment
                else 0.0,
                fallback_used=_fallback_used(
                    context.solo_women_safety_assessment.confidence if context.solo_women_safety_assessment else 0.0
                ),
            ),
        ),
        "review_and_consistency_agent": AgentDefinition(
            name="review_and_consistency_agent",
            responsibility="Review the composed plan for consistency, conflicts, and approval readiness.",
            input_model=ReviewInput,
            output_model=ReviewOutput,
            allowed_tools=("json_completion",),
            build_input=lambda context: ReviewInput(
                request=context.request,
                itinerary_plan=context.itinerary_plan,
            ),
            build_output=lambda context: ReviewOutput(
                review_assessment=context.review_assessment,
                confidence=context.review_assessment.confidence if context.review_assessment else 0.0,
                fallback_used=_fallback_used(context.review_assessment.confidence if context.review_assessment else 0.0),
            ),
        ),
        "governance_gate_agent": AgentDefinition(
            name="governance_gate_agent",
            responsibility="Apply governance policy before a plan can be treated as final output.",
            input_model=GovernanceInput,
            output_model=GovernanceOutput,
            allowed_tools=(),
            build_input=lambda context: GovernanceInput(
                request=context.request,
                review_assessment=context.review_assessment,
                governance_flags=context.governance_flags,
                confidence=context.review_assessment.confidence if context.review_assessment else 0.0,
            ),
            build_output=lambda context: GovernanceOutput(
                review_assessment=context.review_assessment,
                governance_flags=context.governance_flags,
                confidence=context.review_assessment.confidence if context.review_assessment else 0.0,
                fallback_used=not bool(context.review_assessment.approved) if context.review_assessment else True,
            ),
        ),
    }
