# Architecture

This project is a full-stack travel planning demo with a `React` frontend and a `FastAPI` backend. The backend uses `LangGraph` to orchestrate a multi-step planning workflow that combines deterministic validation, external research, and LLM-based synthesis.

This document describes the current runtime. The target autonomous redesign is documented separately in [true-multi-agent-architecture.md](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/docs/true-multi-agent-architecture.md).

## High-Level View

```text
Frontend (React)
  -> POST /api/trips
Backend API (FastAPI)
  -> TravelPlannerService
  -> TravelPlannerGraph (LangGraph)
  -> Shared Planner State
  -> Planner Nodes / Agents
  -> CreateTripResponse
Frontend renders returned planning artifacts
```

## Main Layers

### 1. Frontend

The frontend lives in `frontend/src`.

Its main responsibilities are:

- collect trip inputs
- call the backend `POST /api/trips`
- persist the request/response in local storage
- render the returned planning outputs across the workflow pages

The planner client and shared response types live in [frontend/src/lib/planner.ts](/Users/naveen.kumar.p/Desktop/travel-planner-agent/frontend/src/lib/planner.ts:1).

Important frontend pages:

- `new-trip`
- `clarification`
- `research`
- `itinerary`
- `budget`
- `review`

### 2. Backend API

The backend API lives in `backend/src`.

Entrypoints:

- [backend/src/main.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/main.py:1)
- [backend/src/api/main.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/api/main.py:1)

The backend currently exposes:

- `GET /api/health`
- `POST /api/trips`

`main.py` sets up:

- `FastAPI`
- CORS for local frontend origins
- router mounting

### 3. Service Layer

The service layer is intentionally thin.

Main service:

- [backend/src/services/travel_planner_service.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/services/travel_planner_service.py:1)

Responsibilities:

- create a `trip_id`
- bootstrap the graph with the incoming `TripRequest`
- transform the final planner context into `CreateTripResponse`

The service does not implement the planning logic itself. It delegates orchestration to the graph.

### 4. Orchestration Layer

The orchestration layer is implemented with `LangGraph` in:

- [backend/src/agents/travel_planner/graph.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/graph.py:1)

This is the workflow backbone of the backend.

Responsibilities:

- register each validator/agent as a graph node
- define the execution order
- apply the clarification branch
- invoke the full planner workflow

The current graph is sequential after clarification, with one conditional route:

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

### 5. Shared State Layer

Shared planner state is defined in:

- [backend/src/agents/travel_planner/state.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/state.py:1)

It contains:

- `PlannerContext`: the object used by node implementations
- `PlannerState`: the `LangGraph` state shape

The planner uses state-based communication, not direct agent messaging.

Each node:

1. reads the current shared state
2. consumes prior outputs
3. writes its own output back into shared state
4. updates `status` and `route_trace`

Important shared fields:

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
- `route_trace`

### 6. Agent / Node Layer

The node implementations live in:

- [backend/src/agents/travel_planner/nodes.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:1)

Current nodes:

1. `ClarificationValidator`
2. `ResearchSignalAgent`
3. `DestinationResearchAgent`
4. `ItineraryPlanningAgent`
5. `StayRecommendationAgent`
6. `LocalTransportAgent`
7. `FoodRecommendationAgent`
8. `BudgetOptimizationAgent`
9. `SoloWomenSafetyAdvisorAgent`
10. `ReviewAndConsistencyAgent`

These nodes are bounded units of work. They are not autonomous free-running agents.

Their outputs are typed through the models in:

- [backend/src/agents/travel_planner/schemas.py](/Users/naveen.kumar.p/Desktop/travel-planner-agent/backend/src/agents/travel_planner/schemas.py:1)

### 7. Prompt / Tool Integration Layer

Prompt builders live in:

- `backend/src/agents/travel_planner/research_prompts.py`

External tool/API clients live in:

- `backend/src/agents/travel_planner/research_clients.py`

The system currently uses:

- `OpenAI`
- `Tavily`
- `WeatherAPI`

The rough division of responsibility is:

- `WeatherAPI` for weather context
- `Tavily` for destination and planning research
- `OpenAI` for structured synthesis and plan generation

## Request Lifecycle

The main request flow is:

1. Frontend sends a `TripRequest` to `POST /api/trips`
2. FastAPI passes the request to `TravelPlannerService`
3. The service creates a `trip_id`
4. `TravelPlannerGraph` bootstraps a `PlannerContext`
5. `LangGraph` executes the planner nodes in order
6. Each node reads/writes shared planner state
7. The final context is converted to `CreateTripResponse`
8. The frontend stores and renders the returned response

## Data Model Shape

The core request model is `TripRequest`.

It includes:

- origin city
- destination
- travel dates
- traveler count
- trip purpose
- total budget
- budget tier
- pace
- interests
- accommodation preference
- transport preference
- traveler constraints

The main response model is `CreateTripResponse`.

It can include:

- trip summary
- clarification questions
- destination research
- itinerary plan
- stay recommendation plan
- local transport plan
- food recommendation plan
- budget assessment
- solo women safety assessment
- review assessment
- route trace

## Connectivity Between Components

The component boundaries are:

- frontend talks only to backend API
- API delegates only to service layer
- service delegates only to graph
- graph orchestrates nodes
- nodes communicate only through shared state

This keeps responsibilities separated:

- UI stays presentation-focused
- API stays transport-focused
- service stays response-focused
- graph stays orchestration-focused
- nodes stay planning-focused

## Current Architectural Characteristics

What is strong in the current design:

- clear backend entrypoint
- typed request/response models
- explicit graph orchestration
- shared-state communication between nodes
- bounded responsibilities per node
- frontend is already wired to the real backend response

Current limitations:

- graph execution is mostly sequential after clarification
- no persistence layer or database
- no background job processing
- no caching of research/tool results
- no booking-grade live supplier integrations
- no exact maps/routing provider
- no human review checkpoint inside the graph

## Current Layer Maturity

The current codebase does not cover all enterprise layers equally. Some layers are already visible and reasonably structured, while others are still missing.

| Layer | Current Status | Notes |
| --- | --- | --- |
| Presentation Layer | Present | The React frontend is clearly separated and renders backend planner artifacts well, but it still uses local storage instead of real user/session state. |
| API Layer | Present but basic | FastAPI routes are clean and thin, but there is no authentication, rate limiting, versioning strategy, or hardened error policy yet. |
| Application / Orchestration Layer | Present and relatively strong | `TravelPlannerService` plus `LangGraph` orchestration is one of the better parts of the codebase, but execution is still synchronous and mostly sequential. |
| Domain Layer | Weak / partial | Domain concepts exist in schemas, validators, and helpers, but the business rules are not yet consolidated into a dedicated domain layer. |
| Agent / Decision Layer | Present | The planner nodes are clearly separated by responsibility, but some logic is still coupled to orchestration and provider details. |
| Integration / Provider Layer | Present but narrow | OpenAI, Tavily, and WeatherAPI integrations exist, but provider resilience, fallback policy, and normalization are still limited. |
| Persistence Layer | Missing | There is no database, no repository layer, no persisted planner state, and no execution checkpoint storage. |
| Messaging / Async Processing Layer | Missing | Planner execution is still request-response based with no queue, workers, or background jobs. |
| Security Layer | Mostly missing | There is basic env configuration and CORS, but no auth, authz, secrets manager, audit controls, or abuse protection. |
| Observability Layer | Missing | `route_trace` helps debugging, but there are no structured logs, metrics, traces, alerts, or provider cost monitoring. |
| Configuration Layer | Present but basic | Environment-based config exists, but there is no multi-environment strategy, feature flags, or advanced provider routing. |
| Testing / Quality Layer | Weak | Compile/build checks exist, but there is no real unit, integration, contract, or resilience test coverage. |

### Summary Of Maturity

Strongest layers today:

- Presentation Layer
- API Layer for prototype scope
- Application / Orchestration Layer
- Agent / Decision Layer

Weak but present:

- Domain Layer
- Integration / Provider Layer
- Configuration Layer

Major missing layers:

- Persistence Layer
- Messaging / Async Processing Layer
- Security Layer
- Observability Layer
- Testing / Quality Layer

## Future Improvement Directions

Likely next architectural improvements:

- parallelize stay/transport/food enrichment branches in `LangGraph`
- add persistence for trips and planner artifacts
- add caching for Tavily/weather/tool results
- add stronger destination normalization and geocoding
- add retry/failure policies around external API calls
- add a dedicated final assembler or post-processing node if the response grows further

## Related Documents

- [API Contract](api-contract.md)
- [Agent Flow](agent-flow.md)
- [Agent Communication](agent-communication.md)
