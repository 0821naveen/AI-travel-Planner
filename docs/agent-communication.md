# Agent Communication And Connectivity

This document explains how the backend planner nodes are connected and how data moves from one node to the next.

## Orchestrator

The planner is orchestrated by `LangGraph` in [backend/src/agents/travel_planner/graph.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/graph.py:1).

It uses:

- `StateGraph(PlannerState)` as the workflow container
- one node per validator/agent
- one conditional route after clarification
- a shared state object for node-to-node communication

There is no direct agent-to-agent chat or message bus. Communication happens by reading and writing shared planner state.

## Shared State

The shared state lives in [backend/src/agents/travel_planner/state.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/state.py:1).

Two structures matter:

- `PlannerContext`
- `PlannerState`

`PlannerContext` is the Python object each node works with.
`PlannerState` is the `LangGraph` state shape passed between nodes.

The graph wrapper converts between them:

- `planner_context_from_state(...)`
- `planner_state_from_context(...)`

Important shared fields:

- `request`
- `status`
- `clarification_questions`
- `research_signals`
- `destination_research`
- `itinerary_plan`
- `stay_recommendation_plan`
- `local_transport_plan`
- `food_recommendation_plan`
- `budget_assessment`
- `solo_women_safety_assessment`
- `review_assessment`
- `itinerary_notes`
- `budget_warnings`
- `review_notes`
- `route_trace`

## How Communication Works

Each node follows the same pattern:

1. Read the current `PlannerState`
2. Convert it to `PlannerContext`
3. Inspect fields produced by earlier nodes
4. Add or update its own output fields
5. Update `status` if needed
6. Append its name to `route_trace`
7. Convert back to `PlannerState`

This means each downstream node depends on the structured outputs of earlier nodes, not on free-form conversation.

## Current Graph Connection

The current `LangGraph` flow is:

```text
START
  -> clarification_validator
     -> awaiting_clarification -> END
     -> research_ready -> research_signal_agent
        -> destination_research_agent
        -> itinerary_planning_agent
        -> stay_recommendation_agent
        -> local_transport_agent
        -> food_recommendation_agent
        -> budget_optimization_agent
        -> solo_women_safety_advisor_agent
        -> review_and_consistency_agent
        -> END
```

The conditional branch is implemented through [backend/src/agents/travel_planner/routing.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/routing.py:1):

- if `clarification_questions` is non-empty, status becomes `AWAITING_CLARIFICATION`
- otherwise status becomes `RESEARCH_READY`

## Node By Node Dependencies

### 1. `ClarificationValidator`

Defined in [backend/src/agents/travel_planner/nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:57).

Reads:

- `request`

Writes:

- `clarification_questions`
- `status`
- `route_trace`

Purpose:

- checks whether the trip request has enough structured input to continue

### 2. `ResearchSignalAgent`

Defined in [nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:130).

Reads:

- `request`

Writes:

- `research_signals`
- `status`
- `route_trace`

Purpose:

- derives basic signals such as trip duration and budget-per-day style helpers

### 3. `DestinationResearchAgent`

Defined in [nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:150).

Reads:

- `request`
- `research_signals`

Writes:

- `destination_research`
- `status`
- `route_trace`

Purpose:

- uses WeatherAPI, Tavily, and OpenAI to produce a destination research brief

### 4. `ItineraryPlanningAgent`

Defined in [nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:379).

Reads:

- `request`
- `research_signals`
- `destination_research`

Writes:

- `itinerary_plan`
- `itinerary_notes`
- `status`
- `route_trace`

Purpose:

- creates the first itinerary draft

### 5. `StayRecommendationAgent`

Defined in [nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:562).

Reads:

- `request`
- `destination_research`
- `itinerary_plan`

Writes:

- `stay_recommendation_plan`
- `status`
- `route_trace`

Purpose:

- adds hotel / homestay / area recommendations that fit the itinerary

### 6. `LocalTransportAgent`

Defined in [nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:694).

Reads:

- `request`
- `destination_research`
- `itinerary_plan`

Writes:

- `local_transport_plan`
- `status`
- `route_trace`

Purpose:

- adds movement guidance, suggested transport modes, and approximate fares

### 7. `FoodRecommendationAgent`

Defined in [nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:823).

Reads:

- `request`
- `destination_research`
- `itinerary_plan`

Writes:

- `food_recommendation_plan`
- `status`
- `route_trace`

Purpose:

- adds food suggestions that align with the itinerary and trip preferences

### 8. `BudgetOptimizationAgent`

Defined in [nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:947).

Reads:

- `request`
- `research_signals`
- `destination_research`
- `itinerary_plan`
- `stay_recommendation_plan`
- `local_transport_plan`
- `food_recommendation_plan`

Writes:

- `budget_assessment`
- `budget_warnings`
- `status`
- `route_trace`

Purpose:

- checks whether the richer plan fits the stated budget and suggests optimizations

### 9. `SoloWomenSafetyAdvisorAgent`

Defined in [nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:1074).

Reads:

- `request`
- `destination_research`
- `itinerary_plan`

Writes:

- `solo_women_safety_assessment`
- `status`
- `route_trace`

Purpose:

- adds solo-traveler and women-safety guidance as a specialist advisory layer

### 10. `ReviewAndConsistencyAgent`

Defined in [nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:1198).

Reads:

- `request`
- `destination_research`
- `itinerary_plan`
- `budget_assessment`
- `solo_women_safety_assessment`
- `stay_recommendation_plan`
- `local_transport_plan`
- `food_recommendation_plan`

Writes:

- `review_assessment`
- `review_notes`
- `status`
- `route_trace`

Purpose:

- acts as the final quality gate for consistency, feasibility, and user fit

## What “Agent-To-Agent Communication” Means Here

In this backend, agent-to-agent communication is indirect.

It works like this:

- one node produces a structured artifact
- that artifact is stored in shared state
- later nodes read that artifact and build on it

Examples:

- `DestinationResearchAgent` produces `destination_research`
- `ItineraryPlanningAgent` consumes `destination_research`
- `StayRecommendationAgent`, `LocalTransportAgent`, and `FoodRecommendationAgent` consume `itinerary_plan`
- `BudgetOptimizationAgent` consumes itinerary plus stay/transport/food outputs
- `ReviewAndConsistencyAgent` consumes almost all prior outputs

So the communication model is:

- not direct messaging
- not peer-to-peer chat
- not tool-calling each other
- shared-state handoff through `LangGraph`

## Traceability

Each node adds its name to `route_trace` using `context.mark(...)`.

This gives a simple execution trace that is returned in the trip response via [backend/src/services/travel_planner_service.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/services/travel_planner_service.py:1).

That is useful for:

- debugging
- UI progress display
- confirming which nodes actually ran

## Current Limitation

Although the system now uses `LangGraph`, the main flow is still sequential after clarification.

That means:

- the graph is explicit
- the state handoff is clean
- but enrichment and evaluation steps are not yet running as parallel branches

Possible future improvement:

- run `StayRecommendationAgent`, `LocalTransportAgent`, and `FoodRecommendationAgent` as parallel branches
- then join before `BudgetOptimizationAgent`

## Summary

The planner uses `LangGraph` for orchestration, but the communication model is state-driven rather than conversational.

The connection pattern is:

- one node writes structured outputs
- downstream nodes read those outputs
- the full chain is visible in `graph.py`
- the execution history is visible in `route_trace`
