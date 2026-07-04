from __future__ import annotations

from dataclasses import dataclass
from typing import List

from src.agents.travel_planner.prompts import CLARIFICATION_PROMPTS
from src.agents.travel_planner.schemas import ClarificationQuestion, TripRequest, TripStatus
from src.agents.travel_planner.tools import trip_days


@dataclass(frozen=True)
class ClarificationPolicy:
    max_questions: int = 5
    blocking_keys: tuple[str, ...] = (
        "interests",
        "transport_preference",
        "accommodation_preference",
        "travel_dates",
    )

    def build_questions(self, request: TripRequest) -> List[ClarificationQuestion]:
        questions: List[ClarificationQuestion] = []

        if not request.interests:
            prompt = CLARIFICATION_PROMPTS["interests"]
            questions.append(self._question("interests", prompt["question"], prompt["reason"]))

        if not request.transport_preference:
            prompt = CLARIFICATION_PROMPTS["transport_preference"]
            questions.append(self._question("transport_preference", prompt["question"], prompt["reason"]))

        if not request.accommodation_preference:
            prompt = CLARIFICATION_PROMPTS["accommodation_preference"]
            questions.append(self._question("accommodation_preference", prompt["question"], prompt["reason"]))

        if trip_days(request.start_date, request.end_date) <= 0:
            questions.append(
                self._question(
                    "travel_dates",
                    "Please confirm valid start and end travel dates (YYYY-MM-DD).",
                    "Invalid or reversed dates block feasibility checks and routing.",
                )
            )

        constraints = request.constraints
        if not constraints.dietary_restrictions and not constraints.accessibility_needs and not constraints.notes:
            questions.append(
                self._question(
                    "special_constraints",
                    "Any dietary, accessibility, or mobility constraints we must account for?",
                    "Constraint details reduce unusable recommendations.",
                )
            )

        return questions[: self.max_questions]

    def status_for(self, questions: List[ClarificationQuestion]) -> TripStatus:
        blocking_questions = [question for question in questions if question.key in self.blocking_keys]
        return TripStatus.AWAITING_CLARIFICATION if blocking_questions else TripStatus.RESEARCH_READY

    @staticmethod
    def _question(key: str, question: str, reason: str) -> ClarificationQuestion:
        return ClarificationQuestion(key=key, question=question, reason=reason)
