# Agent Flow

This document describes the current planner flow and the design of each node in the backend workflow.

The workflow is orchestrated with `LangGraph` in [backend/src/agents/travel_planner/graph.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/graph.py:1).

## Flow Overview

```text
START
  -> ClarificationValidator
     -> AWAITING_CLARIFICATION -> END
     -> RESEARCH_READY -> ResearchSignalAgent
        -> DestinationResearchAgent
        -> ItineraryPlanningAgent
        -> StayRecommendationAgent
        -> LocalTransportAgent
        -> FoodRecommendationAgent
        -> BudgetOptimizationAgent
        -> SoloWomenSafetyAdvisorAgent
        -> ReviewAndConsistencyAgent
        -> END
```

## Design Principle

The system does not use free-form agent chat.

Each node:

- reads structured state from `PlannerContext`
- performs one bounded responsibility
- writes its result back into shared state
- updates status when needed
- appends its execution marker into `route_trace`

So the flow is:

- state-driven
- sequential after clarification
- typed with Pydantic schemas

## 1. `ClarificationValidator`

Source:

- [backend/src/agents/travel_planner/nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:57)

Type:

- deterministic validator

Purpose:

- decide whether the request has enough information to proceed into research

Reads:

- `request.interests`
- `request.transport_preference`
- `request.accommodation_preference`
- `request.start_date`
- `request.end_date`
- `request.constraints`

Writes:

- `clarification_questions`
- `status`

Design:

- rule-based, not LLM-based
- uses a small set of missing-field and validity checks
- caps clarification output to a limited number of questions

Why it exists:

- blocks the expensive research/planning steps when the request is too incomplete

Exit behavior:

- if questions exist -> `AWAITING_CLARIFICATION`
- otherwise -> `RESEARCH_READY`

## 2. `ResearchSignalAgent`

Source:

- [backend/src/agents/travel_planner/nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:130)

Type:

- deterministic signal builder

Purpose:

- derive helper values for downstream planning and research

Reads:

- `request.start_date`
- `request.end_date`
- `request.total_budget`
- `request.budget_tier`
- `request.traveler_count`
- `request.trip_purpose`

Writes:

- `research_signals`

Design:

- computes trip duration
- computes budget-per-day style signals
- normalizes a few request fields into a simple dictionary for later agents

Why it exists:

- keeps basic math and normalization out of the LLM-heavy nodes

## 3. `DestinationResearchAgent`

Source:

- [backend/src/agents/travel_planner/nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:150)

Type:

- research + synthesis agent

Purpose:

- gather destination evidence and produce a structured destination brief

Reads:

- `request`
- `research_signals`

Writes:

- `destination_research`
- `status`

Tools:

- `WeatherAPI`
- `Tavily`
- `OpenAI`

Design:

- gathers current weather and near-term forecast signals when possible
- runs a small set of Tavily queries for destination fit, areas, costs, logistics, and highlights
- synthesizes the gathered evidence with OpenAI into a structured `DestinationResearchReport`
- falls back gracefully if a tool is unavailable

Why it exists:

- creates the core research context used by all later planning stages

Downstream consumers:

- `ItineraryPlanningAgent`
- `BudgetOptimizationAgent`
- `SoloWomenSafetyAdvisorAgent`
- `ReviewAndConsistencyAgent`

## 4. `ItineraryPlanningAgent`

Source:

- [backend/src/agents/travel_planner/nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:379)

Type:

- itinerary generation agent

Purpose:

- create the first structured trip plan

Reads:

- `request`
- `research_signals`
- `destination_research`

Writes:

- `itinerary_plan`
- `itinerary_notes`
- `status`

Design:

- uses destination summary, recommended areas, highlights, transport notes, and risk notes
- generates a high-level day-by-day itinerary
- produces one plan entry per day
- includes theme, area, morning/afternoon/evening blocks, pace, cost signal, reasoning, and warnings
- falls back to a simplified plan if model output is missing or invalid

Why it exists:

- creates the itinerary skeleton that later enrichment and evaluation nodes build on

Downstream consumers:

- `StayRecommendationAgent`
- `LocalTransportAgent`
- `FoodRecommendationAgent`
- `BudgetOptimizationAgent`
- `SoloWomenSafetyAdvisorAgent`
- `ReviewAndConsistencyAgent`

## 5. `StayRecommendationAgent`

Source:

- [backend/src/agents/travel_planner/nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:562)

Type:

- itinerary enrichment agent

Purpose:

- recommend where the traveler should stay

Reads:

- `request`
- `destination_research`
- `itinerary_plan`

Writes:

- `stay_recommendation_plan`

Tools:

- `OpenAI`
- destination context already researched upstream

Design:

- uses itinerary structure plus recommended destination areas
- proposes hotel / homestay / area recommendations
- returns stay type, area, price band, fit reasoning, safety notes, and booking tips
- falls back if itinerary is missing or the model is unavailable

Why it exists:

- adds stay guidance without overloading the itinerary generator

## 6. `LocalTransportAgent`

Source:

- [backend/src/agents/travel_planner/nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:694)

Type:

- itinerary enrichment agent

Purpose:

- add movement guidance between itinerary areas

Reads:

- `request`
- `destination_research`
- `itinerary_plan`

Writes:

- `local_transport_plan`

Tools:

- `OpenAI`
- destination transport notes already researched upstream

Design:

- examines itinerary days and areas
- generates area-to-area transport legs
- includes primary mode, backup mode, approximate duration, approximate fare, and notes
- keeps this at approximate planning level rather than exact map routing

Why it exists:

- improves itinerary usefulness without requiring a dedicated maps/routing stack yet

## 7. `FoodRecommendationAgent`

Source:

- [backend/src/agents/travel_planner/nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:823)

Type:

- itinerary enrichment agent

Purpose:

- suggest food options aligned to the trip plan

Reads:

- `request`
- `destination_research`
- `itinerary_plan`

Writes:

- `food_recommendation_plan`

Tools:

- `OpenAI`

Design:

- uses itinerary day structure and destination context
- produces meal-level suggestions
- includes venue name, area, cuisine type, price level, dietary fit, and rationale
- designed as researched guidance, not guaranteed live availability

Why it exists:

- makes the itinerary more operational and useful to the traveler

## 8. `BudgetOptimizationAgent`

Source:

- [backend/src/agents/travel_planner/nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:947)

Type:

- evaluation / optimization agent

Purpose:

- determine whether the richer plan fits the user’s budget

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

Tools:

- `OpenAI`

Design:

- evaluates the full plan after enrichment
- estimates total and daily cost signals
- identifies cost drivers
- suggests optimization actions
- marks warning state if the budget does not fit well

Why it exists:

- budget evaluation is more accurate after stay, transport, and food details exist

## 9. `SoloWomenSafetyAdvisorAgent`

Source:

- [backend/src/agents/travel_planner/nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:1074)

Type:

- specialist advisory agent

Purpose:

- add solo-travel and women-safety guidance

Reads:

- `request`
- `destination_research`
- `itinerary_plan`

Writes:

- `solo_women_safety_assessment`

Tools:

- `OpenAI`

Design:

- evaluates destination areas, destination risks, and itinerary shape
- produces safe areas, caution areas, night transport guidance, lodging tips, solo-friendly suggestions, and itinerary adjustments
- acts as an advisory specialist rather than changing all itinerary data directly

Why it exists:

- keeps safety-focused guidance explicit and visible rather than burying it inside general review output

## 10. `ReviewAndConsistencyAgent`

Source:

- [backend/src/agents/travel_planner/nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:1198)

Type:

- final review agent

Purpose:

- perform the final quality gate over the full plan

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

Tools:

- `OpenAI`

Design:

- reviews consistency, pacing, fit, and feasibility
- considers the downstream enrichment and budget/safety findings
- produces approval status, summary, strengths, issues, fixes, final notes, and confidence
- is the final decision layer before the response is returned

Why it exists:

- provides one last synthesis step over all produced artifacts

## Flow By Stage

The flow can be viewed in four stages.

### Stage 1. Intake Gate

- `ClarificationValidator`

Goal:

- stop early if the request is incomplete

### Stage 2. Research Foundation

- `ResearchSignalAgent`
- `DestinationResearchAgent`

Goal:

- create normalized planning signals and destination context

### Stage 3. Plan Construction And Enrichment

- `ItineraryPlanningAgent`
- `StayRecommendationAgent`
- `LocalTransportAgent`
- `FoodRecommendationAgent`

Goal:

- build the itinerary skeleton and enrich it with practical detail

### Stage 4. Evaluation And Final Review

- `BudgetOptimizationAgent`
- `SoloWomenSafetyAdvisorAgent`
- `ReviewAndConsistencyAgent`

Goal:

- evaluate affordability, safety, and overall quality before returning the plan

## Why The Order Looks Like This

The order is intentional.

- clarification comes first because incomplete requests should not trigger expensive research
- research happens before itinerary because itinerary quality depends on destination context
- stay/transport/food come after itinerary because they enrich the plan rather than replace it
- budget comes after enrichment because cost fit is clearer once the itinerary is more detailed
- safety and final review happen late because they need the broader plan context

## Current Limitation

The nodes are on `LangGraph`, but they are not yet exploiting parallel branches.

Today:

- the enrichment chain is sequential
- the evaluation chain is sequential

A likely future improvement is:

- run `StayRecommendationAgent`, `LocalTransportAgent`, and `FoodRecommendationAgent` in parallel
- join before `BudgetOptimizationAgent`

## Related Documents

- [Architecture](architecture.md)
- [Agent Communication](agent-communication.md)
- [API Contract](api-contract.md)
