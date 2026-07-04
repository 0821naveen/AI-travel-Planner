from __future__ import annotations

from copy import deepcopy
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.travel_planner.schemas import (
    ClarificationAnswer,
    ClarificationCopilotQuestion,
    ClarificationCopilotRequest,
    ClarificationCopilotResponse,
    ClarificationOption,
    ClarificationProfile,
    TripPurpose,
    TripRequest,
)
from src.providers.llm import OpenAIChatClient
from src.providers.search import TavilyClient


class ClarificationGraphState(TypedDict):
    trip_request: TripRequest
    answers: list[ClarificationAnswer]
    profile: ClarificationProfile
    destination_signals: list[str]
    question: ClarificationCopilotQuestion | None
    ready_to_plan: bool
    answered_count: int
    remaining_questions: int
    summary: str


class ClarificationCopilotService:
    max_questions = 5

    def __init__(
        self,
        *,
        tavily_client: TavilyClient | None = None,
        openai_client: OpenAIChatClient | None = None,
    ) -> None:
        self.tavily_client = tavily_client
        self.openai_client = openai_client
        self.app = self._build_graph()

    def next_turn(self, request: ClarificationCopilotRequest) -> ClarificationCopilotResponse:
        profile, normalized_request = self._apply_answers(request.trip_request, request.answers)
        initial_state: ClarificationGraphState = {
            "trip_request": normalized_request,
            "answers": request.answers,
            "profile": profile,
            "destination_signals": [],
            "question": None,
            "ready_to_plan": False,
            "answered_count": len(request.answers),
            "remaining_questions": 0,
            "summary": "",
        }
        result = self.app.invoke(initial_state)
        return ClarificationCopilotResponse(
            normalized_request=result["trip_request"],
            profile=result["profile"],
            question=result["question"],
            ready_to_plan=result["ready_to_plan"],
            destination_signals=result["destination_signals"],
            answered_count=result["answered_count"],
            remaining_questions=result["remaining_questions"],
            summary=result["summary"],
        )

    def _build_graph(self):
        graph = StateGraph(ClarificationGraphState)
        graph.add_node("fetch_destination_signals", self._fetch_destination_signals)
        graph.add_node("build_next_question", self._build_next_question)
        graph.add_edge(START, "fetch_destination_signals")
        graph.add_edge("fetch_destination_signals", "build_next_question")
        graph.add_edge("build_next_question", END)
        return graph.compile()

    def _fetch_destination_signals(self, state: ClarificationGraphState) -> ClarificationGraphState:
        request = state["trip_request"]
        destination_signals = self._collect_destination_signals(request)
        return {**state, "destination_signals": destination_signals}

    def _build_next_question(self, state: ClarificationGraphState) -> ClarificationGraphState:
        profile = state["profile"]
        request = state["trip_request"]
        question = self._select_next_question(
            request=request,
            profile=profile,
            answered_count=state["answered_count"],
            destination_signals=state["destination_signals"],
        )
        ready_to_plan = question is None
        remaining_questions = max(0, self.max_questions - state["answered_count"] - (0 if ready_to_plan else 1))
        summary = self._build_summary(profile=profile, ready_to_plan=ready_to_plan, destination=request.destination)
        return {
            **state,
            "question": question,
            "ready_to_plan": ready_to_plan,
            "remaining_questions": remaining_questions,
            "summary": summary,
        }

    def _collect_destination_signals(self, request: TripRequest) -> list[str]:
        fallback = [
            f"Keep the questions practical for {request.destination}, not generic travel advice.",
            "Use answers to shape stay area, pace, food, safety, and one memorable highlight.",
        ]
        if self.tavily_client is None:
            return fallback

        interests = ", ".join(request.interests[:3]) or request.trip_purpose.value
        query = (
            f"{request.destination} neighborhoods local experiences food atmosphere safety tips "
            f"for {request.trip_purpose.value} travelers interested in {interests}"
        )

        try:
            payload = self.tavily_client.search(query, max_results=3)
        except Exception:
            return fallback

        signals: list[str] = []
        answer = " ".join(str(payload.get("answer", "")).split())
        if answer:
            signals.append(answer[:220])

        for item in payload.get("results", [])[:3]:
            title = " ".join(str(item.get("title", "")).split())
            snippet = " ".join(str(item.get("content", "")).split())
            if title or snippet:
                signals.append(f"{title}: {snippet[:180]}".strip(": "))

        return signals[:3] or fallback

    def _apply_answers(
        self,
        trip_request: TripRequest,
        answers: list[ClarificationAnswer],
    ) -> tuple[ClarificationProfile, TripRequest]:
        request = trip_request.model_copy(deep=True)
        profile = deepcopy(request.clarification_profile)
        notes = [request.constraints.notes.strip()] if request.constraints.notes else []

        for answer in answers:
            value = " ".join(answer.answer.strip().split())
            lowered = value.lower()
            if not value:
                continue

            if answer.key == "interests" and value not in request.interests:
                request.interests = [*request.interests, value][:10]
            elif answer.key == "occasion_type":
                profile.occasion_type = value
                if lowered == "honeymoon":
                    request.trip_purpose = TripPurpose.HONEYMOON
            elif answer.key == "memory_priorities":
                if value.lower() not in {item.lower() for item in profile.memory_priorities}:
                    profile.memory_priorities = [*profile.memory_priorities, value][:5]
            elif answer.key == "celebration_style":
                profile.celebration_style = value
            elif answer.key == "stay_vibe":
                profile.stay_vibe = value
                request.accommodation_preference = self._stay_preference_from_answer(value)
            elif answer.key == "night_comfort":
                profile.night_comfort = value
                if not request.transport_preference:
                    request.transport_preference = self._transport_preference_from_answer(value)
            elif answer.key == "food_focus":
                profile.food_focus = value
            elif answer.key == "must_have_moment":
                profile.must_have_moment = value
            elif answer.key == "local_area_style":
                profile.local_area_style = value

        notes.extend(profile.summary_lines())
        deduped_notes: list[str] = []
        for note in notes:
            cleaned = " ".join(note.split())
            if cleaned and cleaned.lower() not in {item.lower() for item in deduped_notes}:
                deduped_notes.append(cleaned)
        request.constraints.notes = " | ".join(deduped_notes)[:500] if deduped_notes else None
        request.clarification_profile = profile
        return profile, request

    def _select_next_question(
        self,
        *,
        request: TripRequest,
        profile: ClarificationProfile,
        answered_count: int,
        destination_signals: list[str],
    ) -> ClarificationCopilotQuestion | None:
        if answered_count >= self.max_questions:
            return None

        context = destination_signals[:2]

        if not request.interests:
            return ClarificationCopilotQuestion(
                key="interests",
                prompt=f"What do you most want this {request.destination} trip to feel known for?",
                reason="This tells the planner which experience should win when time or budget forces tradeoffs.",
                options=[
                    ClarificationOption(label="Local food", value="Local food"),
                    ClarificationOption(label="Scenic views and photos", value="Scenic views and photos"),
                    ClarificationOption(label="Culture and history", value="Culture and history"),
                    ClarificationOption(label="Relaxed downtime", value="Relaxed downtime"),
                ],
                helper_text="Choose the strongest travel intent. You can still add a custom answer.",
                destination_context=context,
            )

        if not profile.occasion_type:
            return ClarificationCopilotQuestion(
                key="occasion_type",
                prompt="Is this trip a special or memory-first occasion?",
                reason="If the trip is special, the planner should protect meaningful moments instead of optimizing only for logistics.",
                options=[
                    ClarificationOption(label="No, regular trip", value="No special occasion"),
                    ClarificationOption(label="Birthday", value="Birthday"),
                    ClarificationOption(label="Anniversary", value="Anniversary"),
                    ClarificationOption(label="Honeymoon", value="Honeymoon"),
                ],
                helper_text="Use custom if the occasion is something like a proposal, reunion, or reset trip.",
                destination_context=context,
            )

        if profile.occasion_type.lower() != "no special occasion" and not profile.memory_priorities:
            return ClarificationCopilotQuestion(
                key="memory_priorities",
                prompt="What kind of memory matters most on this trip?",
                reason="This helps the itinerary, stay, and food agents bias toward moments that feel worth remembering.",
                options=[
                    ClarificationOption(label="Beautiful photos", value="Beautiful photos"),
                    ClarificationOption(label="Quality time", value="Quality time"),
                    ClarificationOption(label="Unique local experiences", value="Unique local experiences"),
                    ClarificationOption(label="One memorable meal", value="One memorable meal"),
                ],
                destination_context=context,
            )

        if not profile.stay_vibe and not request.accommodation_preference:
            return ClarificationCopilotQuestion(
                key="stay_vibe",
                prompt=f"What kind of stay base would feel right in {request.destination}?",
                reason="Stay vibe directly changes which area and property style the planner should prioritize.",
                options=[
                    ClarificationOption(label="Walkable central base", value="Walkable central base"),
                    ClarificationOption(label="Quiet scenic retreat", value="Quiet scenic retreat"),
                    ClarificationOption(label="Design or boutique stay", value="Design or boutique stay"),
                    ClarificationOption(label="Full-service comfort", value="Full-service comfort"),
                ],
                destination_context=context,
            )

        if not profile.night_comfort and not request.transport_preference:
            return ClarificationCopilotQuestion(
                key="night_comfort",
                prompt=f"How comfortable are you with being out after dark in {request.destination}?",
                reason="This changes transport advice, area selection, and how late the itinerary should run.",
                options=[
                    ClarificationOption(label="Mostly daytime plans", value="Mostly daytime plans"),
                    ClarificationOption(label="Some evenings with cabs", value="Some evenings with cabs"),
                    ClarificationOption(label="Late nights are fine", value="Late nights are fine"),
                    ClarificationOption(label="Need easy door-to-door comfort", value="Need easy door-to-door comfort"),
                ],
                destination_context=context,
            )

        if not profile.food_focus:
            return ClarificationCopilotQuestion(
                key="food_focus",
                prompt="Which food angle should the planner care about most?",
                reason="This helps the food agent choose between practical meals, a signature dinner, or destination-specific food moments.",
                options=[
                    ClarificationOption(label="Street food and local classics", value="Street food and local classics"),
                    ClarificationOption(label="One memorable dinner", value="One memorable dinner"),
                    ClarificationOption(label="Dietary-safe reliable picks", value="Dietary-safe reliable picks"),
                    ClarificationOption(label="Trendy cafes and rooftops", value="Trendy cafes and rooftops"),
                ],
                destination_context=context,
            )

        if profile.occasion_type.lower() != "no special occasion" and not profile.celebration_style:
            return ClarificationCopilotQuestion(
                key="celebration_style",
                prompt="How visible should the celebration feel?",
                reason="This determines whether the planner should add quiet premium touches or build one obvious highlight around the occasion.",
                options=[
                    ClarificationOption(label="Subtle and low-key", value="Subtle and low-key"),
                    ClarificationOption(label="One standout moment", value="One standout moment"),
                    ClarificationOption(label="Full celebration energy", value="Full celebration energy"),
                    ClarificationOption(label="Flexible surprise element", value="Flexible surprise element"),
                ],
                destination_context=context,
            )

        if not profile.must_have_moment:
            return ClarificationCopilotQuestion(
                key="must_have_moment",
                prompt="What is one moment the planner should protect on this trip?",
                reason="A protected moment keeps the itinerary from becoming efficient but forgettable.",
                options=[
                    ClarificationOption(label="Sunset or scenic moment", value="Sunset or scenic moment"),
                    ClarificationOption(label="Special dinner", value="Special dinner"),
                    ClarificationOption(label="Beautiful stay experience", value="Beautiful stay experience"),
                    ClarificationOption(label="A slow unscheduled block", value="A slow unscheduled block"),
                ],
                destination_context=context,
            )

        return None

    @staticmethod
    def _stay_preference_from_answer(answer: str) -> str:
        mapping = {
            "walkable central base": "Walkable central neighborhoods close to food and transit",
            "quiet scenic retreat": "Quiet scenic stay with lower noise and stronger ambiance",
            "design or boutique stay": "Boutique or design-led stay with strong character",
            "full-service comfort": "Full-service hotel with reliable comfort and amenities",
        }
        return mapping.get(answer.lower(), answer)

    @staticmethod
    def _transport_preference_from_answer(answer: str) -> str:
        mapping = {
            "mostly daytime plans": "Walkable areas and daytime public transport are preferred",
            "some evenings with cabs": "Public transport by day and prebooked cabs after dark",
            "late nights are fine": "Flexible transport mix including late evening returns",
            "need easy door-to-door comfort": "Direct taxis or rideshare for most movements",
        }
        return mapping.get(answer.lower(), answer)

    @staticmethod
    def _build_summary(*, profile: ClarificationProfile, ready_to_plan: bool, destination: str) -> str:
        if ready_to_plan:
            return f"Clarification is complete. The planner can now start with a more tailored brief for {destination}."
        if profile.occasion_type and profile.occasion_type.lower() != "no special occasion":
            return "The copilot is shaping this as a memory-first trip, not a generic itinerary."
        return "The copilot is filling the few details that will most change planning quality."
