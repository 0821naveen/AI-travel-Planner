from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from src.agents.travel_planner.schemas import (
    BudgetAssessment,
    ClarificationQuestion,
    DestinationResearchReport,
    EvidenceItem,
    FoodRecommendationPlan,
    HumanApprovalRecord,
    HumanApprovalStatus,
    ItineraryPlan,
    LocalTransportPlan,
    ReviewAssessment,
    SoloWomenSafetyAssessment,
    StayRecommendationPlan,
    TripRequest,
    TripStatus,
)
from src.db.models import TripRecordModel
from src.domain.trips.models import TripRecord
from src.domain.trips.repositories import TripRepository


class PostgresTripRepository(TripRepository):
    def __init__(self, *, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def save(self, trip: TripRecord) -> TripRecord:
        with self.session_factory() as session:
            record = session.get(TripRecordModel, trip.trip_id)
            if record is None:
                record = TripRecordModel(trip_id=trip.trip_id)

            record.request_json = trip.request.model_dump_json()
            record.status = trip.status.value
            record.created_at = trip.created_at
            record.updated_at = trip.updated_at
            record.run_id = trip.run_id
            record.state_version = trip.state_version
            record.clarification_needed = trip.clarification_needed
            record.clarification_questions_json = self._dump_many(trip.clarification_questions)
            record.destination_research_json = self._dump_optional(trip.destination_research)
            record.itinerary_plan_json = self._dump_optional(trip.itinerary_plan)
            record.stay_recommendation_plan_json = self._dump_optional(trip.stay_recommendation_plan)
            record.local_transport_plan_json = self._dump_optional(trip.local_transport_plan)
            record.food_recommendation_plan_json = self._dump_optional(trip.food_recommendation_plan)
            record.budget_assessment_json = self._dump_optional(trip.budget_assessment)
            record.solo_women_safety_assessment_json = self._dump_optional(trip.solo_women_safety_assessment)
            record.review_assessment_json = self._dump_optional(trip.review_assessment)
            record.approval_status = trip.human_approval.status.value
            record.approval_actor_id = trip.human_approval.reviewer_actor_id
            record.approval_actor_role = trip.human_approval.reviewer_role
            record.approval_reviewed_at = trip.human_approval.reviewed_at
            record.approval_note = trip.human_approval.note
            record.evidence_items_json = self._dump_many(trip.evidence_items)
            record.route_trace_json = self._dump_json_list(trip.route_trace)
            record.workflow_state_json = trip.workflow_state_json
            record.node_outputs_json = json.dumps(trip.node_outputs)
            record.governance_flags_json = self._dump_json_list(trip.governance_flags)
            record.short_term_memory_json = json.dumps(trip.short_term_memory)
            record.run_summary_json = json.dumps(trip.run_summary)

            session.add(record)
            session.commit()

        return trip

    def get(self, trip_id: str) -> Optional[TripRecord]:
        with self.session_factory() as session:
            record = session.get(TripRecordModel, trip_id)
            return self._to_domain(record)

    def list_recent(self, limit: int = 20) -> list[TripRecord]:
        with self.session_factory() as session:
            statement = select(TripRecordModel).order_by(TripRecordModel.updated_at.desc()).limit(limit)
            return [self._to_domain(record) for record in session.execute(statement).scalars() if record is not None]

    def list_review_queue(self, limit: int = 20) -> list[TripRecord]:
        with self.session_factory() as session:
            statement = (
                select(TripRecordModel)
                .where(TripRecordModel.approval_status.in_(["pending", "rejected"]))
                .order_by(TripRecordModel.updated_at.desc())
                .limit(limit)
            )
            return [self._to_domain(record) for record in session.execute(statement).scalars() if record is not None]

    @staticmethod
    def _dump_optional(value) -> Optional[str]:
        return value.model_dump_json() if value is not None else None

    @staticmethod
    def _dump_many(values) -> str:
        return PostgresTripRepository._dump_json_list([item.model_dump() for item in values])

    @staticmethod
    def _dump_json_list(values) -> str:
        return json.dumps(values)

    @staticmethod
    def _load_optional(model_cls, value: Optional[str]):
        return model_cls.model_validate_json(value) if value else None

    @staticmethod
    def _load_many(model_cls, value: str):
        raw = json.loads(value or "[]")
        if model_cls is str:
            return list(raw)
        return [model_cls.model_validate(item) for item in raw]

    def _to_domain(self, record: TripRecordModel | None) -> Optional[TripRecord]:
        if record is None:
            return None
        return TripRecord(
            trip_id=record.trip_id,
            request=TripRequest.model_validate_json(record.request_json),
            status=TripStatus(record.status),
            created_at=record.created_at,
            updated_at=record.updated_at,
            run_id=record.run_id,
            state_version=record.state_version,
            clarification_needed=record.clarification_needed,
            clarification_questions=self._load_many(ClarificationQuestion, record.clarification_questions_json),
            destination_research=self._load_optional(DestinationResearchReport, record.destination_research_json),
            itinerary_plan=self._load_optional(ItineraryPlan, record.itinerary_plan_json),
            stay_recommendation_plan=self._load_optional(StayRecommendationPlan, record.stay_recommendation_plan_json),
            local_transport_plan=self._load_optional(LocalTransportPlan, record.local_transport_plan_json),
            food_recommendation_plan=self._load_optional(FoodRecommendationPlan, record.food_recommendation_plan_json),
            budget_assessment=self._load_optional(BudgetAssessment, record.budget_assessment_json),
            solo_women_safety_assessment=self._load_optional(
                SoloWomenSafetyAssessment, record.solo_women_safety_assessment_json
            ),
            review_assessment=self._load_optional(ReviewAssessment, record.review_assessment_json),
            human_approval=HumanApprovalRecord(
                status=HumanApprovalStatus(record.approval_status),
                reviewer_actor_id=record.approval_actor_id,
                reviewer_role=record.approval_actor_role,
                reviewed_at=record.approval_reviewed_at,
                note=record.approval_note,
            ),
            evidence_items=self._load_many(EvidenceItem, record.evidence_items_json),
            route_trace=self._load_many(str, record.route_trace_json),
            workflow_state_json=record.workflow_state_json,
            node_outputs=json.loads(record.node_outputs_json or "{}"),
            governance_flags=self._load_many(str, record.governance_flags_json),
            short_term_memory=json.loads(record.short_term_memory_json or "{}"),
            run_summary=json.loads(record.run_summary_json or "{}"),
        )
