from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class TripStatus(str, Enum):
    DRAFT = "draft"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    RESEARCH_READY = "research_ready"
    RESEARCH_COMPLETE = "research_complete"
    ITINERARY_READY = "itinerary_ready"
    BUDGET_WARNING = "budget_warning"
    READY_FOR_REVIEW = "ready_for_review"
    COMPLETED = "completed"


class BudgetTier(str, Enum):
    BUDGET = "budget"
    MID_RANGE = "mid_range"
    PREMIUM = "premium"
    LUXURY = "luxury"


class TripPurpose(str, Enum):
    LEISURE = "leisure"
    FAMILY = "family"
    WORKATION = "workation"
    HONEYMOON = "honeymoon"
    ADVENTURE = "adventure"


class TravelerConstraints(BaseModel):
    dietary_restrictions: List[str] = Field(default_factory=list)
    accessibility_needs: List[str] = Field(default_factory=list)
    visa_required: Optional[bool] = None
    child_friendly: bool = False
    elderly_travelers: bool = False
    remote_work_needs: bool = False
    notes: Optional[str] = None

    @field_validator("dietary_restrictions", "accessibility_needs", mode="before")
    @classmethod
    def normalize_string_lists(cls, value: object) -> List[str]:
        if value is None:
            return []
        items = value if isinstance(value, list) else [value]
        normalized: list[str] = []
        for item in items:
            cleaned = " ".join(str(item).strip().split())
            if cleaned and cleaned.lower() not in {entry.lower() for entry in normalized}:
                normalized.append(cleaned)
        return normalized

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned[:500] if cleaned else None


class TripRequest(BaseModel):
    origin_city: str
    destination: str
    start_date: str
    end_date: str
    traveler_count: int = Field(ge=1)
    trip_purpose: TripPurpose
    total_budget: float = Field(gt=0)
    budget_tier: BudgetTier
    pace: str
    interests: List[str] = Field(default_factory=list)
    accommodation_preference: Optional[str] = None
    transport_preference: Optional[str] = None
    constraints: TravelerConstraints = Field(default_factory=TravelerConstraints)
    clarification_profile: "ClarificationProfile" = Field(default_factory=lambda: ClarificationProfile())

    @field_validator(
        "origin_city",
        "destination",
        "start_date",
        "end_date",
        "pace",
        "accommodation_preference",
        "transport_preference",
        mode="before",
    )
    @classmethod
    def normalize_text_fields(cls, value: object) -> object:
        if value is None:
            return None
        return " ".join(str(value).strip().split())

    @field_validator("interests", mode="before")
    @classmethod
    def normalize_interests(cls, value: object) -> List[str]:
        if value is None:
            return []
        items = value if isinstance(value, list) else [value]
        normalized: list[str] = []
        for item in items:
            cleaned = " ".join(str(item).strip().split())
            if cleaned and cleaned.lower() not in {entry.lower() for entry in normalized}:
                normalized.append(cleaned)
        return normalized[:10]

    @field_validator("pace")
    @classmethod
    def validate_pace(cls, value: str) -> str:
        allowed = {"relaxed", "balanced", "fast"}
        lowered = value.lower()
        if lowered not in allowed:
            raise ValueError(f"pace must be one of {sorted(allowed)}")
        return lowered

    @model_validator(mode="after")
    def validate_dates(self) -> "TripRequest":
        start = date.fromisoformat(self.start_date)
        end = date.fromisoformat(self.end_date)
        if end < start:
            raise ValueError("end_date must be on or after start_date")
        if (end - start).days > 30:
            raise ValueError("trip duration must not exceed 31 days")
        return self


class ClarificationQuestion(BaseModel):
    key: str
    question: str
    reason: str


class ClarificationOption(BaseModel):
    label: str
    value: str


class ClarificationAnswer(BaseModel):
    key: str
    answer: str

    @field_validator("key", "answer", mode="before")
    @classmethod
    def normalize_answer_fields(cls, value: object) -> str:
        return " ".join(str(value or "").strip().split())


class ClarificationProfile(BaseModel):
    occasion_type: Optional[str] = None
    celebration_style: Optional[str] = None
    memory_priorities: List[str] = Field(default_factory=list)
    surprise_tolerance: Optional[str] = None
    photo_importance: Optional[str] = None
    privacy_preference: Optional[str] = None
    must_have_moment: Optional[str] = None
    night_comfort: Optional[str] = None
    stay_vibe: Optional[str] = None
    food_focus: Optional[str] = None
    local_area_style: Optional[str] = None

    @field_validator(
        "occasion_type",
        "celebration_style",
        "surprise_tolerance",
        "photo_importance",
        "privacy_preference",
        "must_have_moment",
        "night_comfort",
        "stay_vibe",
        "food_focus",
        "local_area_style",
        mode="before",
    )
    @classmethod
    def normalize_profile_text(cls, value: object) -> Optional[str]:
        if value is None:
            return None
        cleaned = " ".join(str(value).strip().split())
        return cleaned or None

    @field_validator("memory_priorities", mode="before")
    @classmethod
    def normalize_memory_priorities(cls, value: object) -> List[str]:
        if value is None:
            return []
        items = value if isinstance(value, list) else [value]
        normalized: list[str] = []
        for item in items:
            cleaned = " ".join(str(item).strip().split())
            if cleaned and cleaned.lower() not in {entry.lower() for entry in normalized}:
                normalized.append(cleaned)
        return normalized[:5]

    def summary_lines(self) -> List[str]:
        lines: list[str] = []
        if self.occasion_type:
            lines.append(f"Occasion: {self.occasion_type}")
        if self.celebration_style:
            lines.append(f"Celebration style: {self.celebration_style}")
        if self.memory_priorities:
            lines.append(f"Memory priorities: {', '.join(self.memory_priorities)}")
        if self.must_have_moment:
            lines.append(f"Must-have moment: {self.must_have_moment}")
        if self.night_comfort:
            lines.append(f"After-dark comfort: {self.night_comfort}")
        if self.stay_vibe:
            lines.append(f"Stay vibe: {self.stay_vibe}")
        if self.food_focus:
            lines.append(f"Food focus: {self.food_focus}")
        if self.local_area_style:
            lines.append(f"Area style: {self.local_area_style}")
        if self.photo_importance:
            lines.append(f"Photo importance: {self.photo_importance}")
        if self.privacy_preference:
            lines.append(f"Privacy preference: {self.privacy_preference}")
        if self.surprise_tolerance:
            lines.append(f"Surprise tolerance: {self.surprise_tolerance}")
        return lines


class ClarificationCopilotQuestion(BaseModel):
    key: str
    prompt: str
    reason: str
    options: List[ClarificationOption] = Field(default_factory=list)
    allow_custom: bool = True
    helper_text: Optional[str] = None
    destination_context: List[str] = Field(default_factory=list)


class ClarificationCopilotRequest(BaseModel):
    trip_request: TripRequest
    answers: List[ClarificationAnswer] = Field(default_factory=list)


class ClarificationCopilotResponse(BaseModel):
    normalized_request: TripRequest
    profile: ClarificationProfile
    question: Optional[ClarificationCopilotQuestion] = None
    ready_to_plan: bool = False
    destination_signals: List[str] = Field(default_factory=list)
    answered_count: int = 0
    remaining_questions: int = 0
    summary: str = ""


class ResearchSource(BaseModel):
    title: str
    url: str
    snippet: str


class WeatherSnapshot(BaseModel):
    location: str
    summary: str
    trip_window: str
    current_temp_c: Optional[float] = None
    forecast_avg_temp_c: Optional[float] = None
    forecast_max_temp_c: Optional[float] = None
    forecast_min_temp_c: Optional[float] = None
    chance_of_rain: Optional[int] = None


class DestinationResearchReport(BaseModel):
    destination: str
    summary: str
    weather: Optional[WeatherSnapshot] = None
    budget_per_day_estimate: Optional[float] = None
    interest_fit: List[str] = Field(default_factory=list)
    recommended_areas: List[str] = Field(default_factory=list)
    local_transport_notes: List[str] = Field(default_factory=list)
    top_highlights: List[str] = Field(default_factory=list)
    top_risks: List[str] = Field(default_factory=list)
    planning_tips: List[str] = Field(default_factory=list)
    hotel_price_signal: Optional[str] = None
    flight_price_signal: Optional[str] = None
    flight_context_summary: str = ""
    assumptions: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
    sources: List[ResearchSource] = Field(default_factory=list)


class ItineraryDayPlan(BaseModel):
    day_number: int = Field(ge=1)
    date: str
    theme: str
    morning: str
    morning_suggestions: List["ItinerarySuggestion"] = Field(default_factory=list)
    afternoon: str
    afternoon_suggestions: List["ItinerarySuggestion"] = Field(default_factory=list)
    evening: str
    evening_suggestions: List["ItinerarySuggestion"] = Field(default_factory=list)
    area: str
    transport_note: str
    recommended_restaurant: str = ""
    restaurant_maps_url: str = ""
    restaurant_website_url: str = ""
    restaurant_review_video_urls: List[str] = Field(default_factory=list)
    best_restaurant_short_url: str = ""
    signature_dishes: List[str] = Field(default_factory=list)
    photo_spot: str = ""
    photo_timing: str = ""
    photo_maps_url: str = ""
    photo_blog_urls: List[str] = Field(default_factory=list)
    photo_vlog_urls: List[str] = Field(default_factory=list)
    best_photo_short_url: str = ""
    pace_level: str
    estimated_daily_cost: str
    reasoning: str
    warnings: List[str] = Field(default_factory=list)


class ItinerarySuggestion(BaseModel):
    title: str
    website_url: str = ""
    maps_url: str = ""


class ItineraryPlan(BaseModel):
    destination: str
    summary: str
    days: List[ItineraryDayPlan] = Field(default_factory=list)
    budget_fit_note: str
    assumptions: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class StayRecommendation(BaseModel):
    name: str
    stay_type: str
    area: str
    price_band: str
    why_fit: str
    safety_notes: List[str] = Field(default_factory=list)
    booking_tips: List[str] = Field(default_factory=list)
    booking_url: str = ""
    maps_url: str = ""
    official_website: str = ""


class StayRecommendationPlan(BaseModel):
    destination: str
    summary: str
    hotel_inventory_summary: str = ""
    traveler_review_summary: str = ""
    recommendations: List[StayRecommendation] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class TransportLegRecommendation(BaseModel):
    day_number: int = Field(ge=1)
    from_area: str
    to_area: str
    recommended_mode: str
    backup_mode: str
    approx_duration: str
    approx_fare: str
    notes: str


class LocalTransportPlan(BaseModel):
    destination: str
    summary: str
    legs: List[TransportLegRecommendation] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class FoodRecommendation(BaseModel):
    day_number: int = Field(ge=1)
    meal: str
    venue_name: str
    area: str
    cuisine_type: str
    price_level: str
    dietary_fit: str
    why_fit: str
    maps_url: str = ""
    official_website: str = ""
    review_video_urls: List[str] = Field(default_factory=list)


class FoodRecommendationPlan(BaseModel):
    destination: str
    summary: str
    traveler_review_summary: str = ""
    recommendations: List[FoodRecommendation] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class BudgetAssessment(BaseModel):
    destination: str
    within_budget: bool
    estimated_total_cost: str
    estimated_daily_cost: str
    summary: str
    cost_drivers: List[str] = Field(default_factory=list)
    optimization_actions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class SoloWomenSafetyAssessment(BaseModel):
    destination: str
    applies: bool
    summary: str
    solo_traveler_fit: str
    women_safety_risk_level: str
    safe_areas: List[str] = Field(default_factory=list)
    caution_areas: List[str] = Field(default_factory=list)
    night_transport_guidance: List[str] = Field(default_factory=list)
    lodging_safety_tips: List[str] = Field(default_factory=list)
    solo_friendly_suggestions: List[str] = Field(default_factory=list)
    itinerary_adjustments: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class ReviewAssessment(BaseModel):
    destination: str
    approved: bool
    summary: str
    consistency_score: float = Field(default=0.5, ge=0, le=1)
    strengths: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    recommended_fixes: List[str] = Field(default_factory=list)
    final_notes: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class HumanApprovalStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class HumanApprovalRecord(BaseModel):
    status: HumanApprovalStatus = HumanApprovalStatus.NOT_REQUIRED
    reviewer_actor_id: Optional[str] = None
    reviewer_role: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    note: Optional[str] = None


class EvidenceItem(BaseModel):
    category: str
    title: str
    detail: str
    url: Optional[str] = None


class TripSummaryResponse(BaseModel):
    trip_id: str
    status: TripStatus
    destination: str
    start_date: str
    end_date: str
    traveler_count: int


class CreateTripResponse(BaseModel):
    run_id: Optional[str] = None
    trip: TripSummaryResponse
    clarification_needed: bool
    clarification_questions: List[ClarificationQuestion] = Field(default_factory=list)
    destination_research: Optional[DestinationResearchReport] = None
    itinerary_plan: Optional[ItineraryPlan] = None
    stay_recommendation_plan: Optional[StayRecommendationPlan] = None
    local_transport_plan: Optional[LocalTransportPlan] = None
    food_recommendation_plan: Optional[FoodRecommendationPlan] = None
    budget_assessment: Optional[BudgetAssessment] = None
    solo_women_safety_assessment: Optional[SoloWomenSafetyAssessment] = None
    review_assessment: Optional[ReviewAssessment] = None
    human_approval: HumanApprovalRecord = Field(default_factory=HumanApprovalRecord)
    evidence_items: List[EvidenceItem] = Field(default_factory=list)
    route_trace: List[str] = Field(default_factory=list)


TripRequest.model_rebuild()
