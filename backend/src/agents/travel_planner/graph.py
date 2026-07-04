from __future__ import annotations

import time
from collections import OrderedDict
from typing import Callable

from langgraph.graph import END, START, StateGraph

from src.agents.travel_planner.contracts import build_agent_definitions
from src.agents.travel_planner.governance import evaluate_governance, should_route_early_to_review
from src.agents.travel_planner.nodes import (
    BudgetOptimizationAgent,
    ClarificationValidator,
    DestinationResearchAgent,
    FoodRecommendationAgent,
    GovernanceGateAgent,
    ItineraryPlanningAgent,
    LocalTransportAgent,
    ResearchSignalAgent,
    ReviewAndConsistencyAgent,
    SoloWomenSafetyAdvisorAgent,
    StayRecommendationAgent,
)
from src.agents.travel_planner.routing import route_after_clarification
from src.agents.travel_planner.schemas import TripRequest, TripStatus
from src.agents.travel_planner.state import (
    PlannerContext,
    PlannerState,
    planner_context_from_state,
    planner_state_from_context,
)


class TravelPlannerGraph:
    def __init__(self) -> None:
        self.clarification_validator = ClarificationValidator()
        self.research_signal_agent = ResearchSignalAgent()
        self.destination_research_agent = DestinationResearchAgent()
        self.itinerary_planning_agent = ItineraryPlanningAgent()
        self.stay_recommendation_agent = StayRecommendationAgent()
        self.local_transport_agent = LocalTransportAgent()
        self.food_recommendation_agent = FoodRecommendationAgent()
        self.budget_optimization_agent = BudgetOptimizationAgent()
        self.solo_women_safety_advisor_agent = SoloWomenSafetyAdvisorAgent()
        self.review_and_consistency_agent = ReviewAndConsistencyAgent()
        self.governance_gate_agent = GovernanceGateAgent()
        self.agent_definitions = build_agent_definitions()
        self.step_handlers = OrderedDict(
            [
                ("clarification_validator", self.clarification_validator.run),
                ("research_signal_agent", self.research_signal_agent.run),
                ("destination_research_agent", self.destination_research_agent.run),
                ("itinerary_planning_agent", self.itinerary_planning_agent.run),
                ("stay_recommendation_agent", self.stay_recommendation_agent.run),
                ("local_transport_agent", self.local_transport_agent.run),
                ("food_recommendation_agent", self.food_recommendation_agent.run),
                ("budget_optimization_agent", self.budget_optimization_agent.run),
                ("solo_women_safety_advisor_agent", self.solo_women_safety_advisor_agent.run),
                ("review_and_consistency_agent", self.review_and_consistency_agent.run),
                ("governance_gate_agent", self.governance_gate_agent.run),
            ]
        )
        self.app = self._build_graph()

    def bootstrap_trip(self, trip_id: str, request: TripRequest, *, run_id: str | None = None) -> PlannerContext:
        context = PlannerContext(trip_id=trip_id, request=request, run_id=run_id, status=TripStatus.DRAFT)
        state = planner_state_from_context(context)
        result = self.app.invoke(state)
        return planner_context_from_state(result)

    def _build_graph(self):
        graph = StateGraph(PlannerState)

        for step_name, step_handler in self.step_handlers.items():
            graph.add_node(step_name, self._wrap_agent(step_name, step_handler))

        graph.add_edge(START, "clarification_validator")
        graph.add_conditional_edges(
            "clarification_validator",
            self._route_after_clarification,
            {
                "awaiting_clarification": END,
                "research_ready": "research_signal_agent",
            },
        )
        graph.add_edge("research_signal_agent", "destination_research_agent")
        graph.add_edge("destination_research_agent", "itinerary_planning_agent")
        graph.add_edge("itinerary_planning_agent", "stay_recommendation_agent")
        graph.add_edge("stay_recommendation_agent", "local_transport_agent")
        graph.add_edge("local_transport_agent", "food_recommendation_agent")
        graph.add_edge("food_recommendation_agent", "budget_optimization_agent")
        graph.add_edge("budget_optimization_agent", "solo_women_safety_advisor_agent")
        graph.add_edge("solo_women_safety_advisor_agent", "review_and_consistency_agent")
        graph.add_edge("review_and_consistency_agent", "governance_gate_agent")
        graph.add_edge("governance_gate_agent", END)

        return graph.compile()

    def initial_step(self) -> str:
        return "clarification_validator"

    def execute_step(self, step_name: str, context: PlannerContext) -> PlannerContext:
        if step_name not in self.step_handlers:
            raise ValueError(f"Unknown workflow step: {step_name}")
        return self._execute_step_with_contracts(step_name, context)

    def next_step(self, step_name: str, context: PlannerContext) -> str | None:
        if step_name == "clarification_validator":
            context.status = route_after_clarification(context)
            if context.status == TripStatus.AWAITING_CLARIFICATION:
                return None
            return "research_signal_agent"

        if should_route_early_to_review(step_name, context):
            context.status = TripStatus.READY_FOR_REVIEW
            return "review_and_consistency_agent"

        if step_name == "review_and_consistency_agent":
            return "governance_gate_agent"

        ordered_steps = list(self.step_handlers.keys())
        index = ordered_steps.index(step_name)
        if index == len(ordered_steps) - 1:
            return None
        return ordered_steps[index + 1]

    def _wrap_agent(self, step_name: str, agent_run: Callable[[PlannerContext], PlannerContext]):
        def _runner(state: PlannerState) -> PlannerState:
            context = planner_context_from_state(state)
            updated_context = self._execute_step_with_contracts(step_name, context)
            return planner_state_from_context(updated_context)

        return _runner

    def _route_after_clarification(self, state: PlannerState) -> str:
        context = planner_context_from_state(state)
        context.status = route_after_clarification(context)
        if context.status == TripStatus.AWAITING_CLARIFICATION:
            return "awaiting_clarification"
        return "research_ready"

    def _execute_step_with_contracts(self, step_name: str, context: PlannerContext) -> PlannerContext:
        definition = self.agent_definitions[step_name]
        definition.build_input(context)
        started = time.perf_counter()
        context.append_audit_event(
            {
                "event_type": "node_started",
                "run_id": context.run_id,
                "trip_id": context.trip_id,
                "node_name": step_name,
            }
        )
        updated_context = self.step_handlers[step_name](context)
        output_contract = definition.build_output(updated_context)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        updated_context.record_node_output(step_name, output_contract.model_dump(mode="json"))
        updated_context.governance_flags = evaluate_governance(updated_context).flags
        updated_context.run_summary[step_name] = {
            "confidence": getattr(output_contract, "confidence", 0.0),
            "fallback_used": getattr(output_contract, "fallback_used", False),
            "duration_ms": duration_ms,
            "status": updated_context.status.value,
        }
        updated_context.append_audit_event(
            {
                "event_type": "node_completed",
                "run_id": updated_context.run_id,
                "trip_id": updated_context.trip_id,
                "node_name": step_name,
                "status": updated_context.status.value,
                "duration_ms": duration_ms,
                "confidence": getattr(output_contract, "confidence", 0.0),
            }
        )
        if getattr(output_contract, "fallback_used", False):
            updated_context.append_audit_event(
                {
                    "event_type": "fallback_used",
                    "run_id": updated_context.run_id,
                    "trip_id": updated_context.trip_id,
                    "node_name": step_name,
                }
            )
        return updated_context
