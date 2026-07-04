# Layered Architecture

This document explains the current application architecture layer by layer and anchors it to the codebase as it exists today.

## Diagram

![Layered Architecture](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/docs/assets/layered-architecture.png)

## Overview

The application is a full-stack travel planning system with:

- a `React` frontend
- a `FastAPI` backend
- a `LangGraph` orchestration layer
- a custom coordinator-driven multi-agent runtime
- external provider/tool integrations
- `Postgres` and `Redis` for persistence and execution infrastructure

The important architectural shift is that the backend is no longer only a fixed sequential planner pipeline. It now also has a coordinator-based runtime that can dispatch specialist agents selectively and run some of them in parallel when dependencies allow it.

## Layer 1: Presentation Layer

This is the user-facing web application.

Main responsibilities:

- collect trip inputs
- submit sync or async trip requests
- show workflow runtime state
- render research, itinerary, budget, and review outputs
- maintain some browser-local state such as the active run id

Main code:

- [frontend/src/App.tsx](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/frontend/src/App.tsx:1)
- [frontend/src/lib/planner.ts](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/frontend/src/lib/planner.ts:1)

Main screens:

- `Dashboard`
- `New Trip`
- `Clarification`
- `Research`
- `Itinerary`
- `Budget`
- `Review`

## Layer 2: API Layer

This is the HTTP boundary of the system.

Main responsibilities:

- receive requests from the frontend
- validate typed request bodies
- apply auth header and role checks
- shape responses
- expose admin, runtime, and observability endpoints

Main code:

- [backend/src/main.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/main.py:1)
- [backend/src/api/main.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/api/main.py:1)

Important endpoints:

- `POST /api/trips`
- `POST /api/trips/async`
- `GET /api/trips/{trip_id}`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/steps`
- `GET /api/admin/*`

## Layer 3: Orchestration Layer

This is the control plane of the backend.

It contains two important pieces:

- `LangGraph` as the orchestrator/runtime framework
- a custom `CoordinatorRuntime` and `CoordinatorAgent`

Main responsibilities:

- decide which agent should act next
- maintain the task board and message ledger
- enforce dependency ordering
- release independent specialists in parallel when appropriate
- keep review and governance as fan-in stages

Main code:

- [backend/src/agents/travel_planner/multi_agent/runtime.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/agents/travel_planner/multi_agent/runtime.py:1)
- [backend/src/agents/travel_planner/multi_agent/coordinator.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/agents/travel_planner/multi_agent/coordinator.py:1)
- [backend/src/agents/travel_planner/multi_agent/schemas.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/agents/travel_planner/multi_agent/schemas.py:1)
- [backend/src/agents/travel_planner/multi_agent/topology.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/agents/travel_planner/multi_agent/topology.py:1)

How it behaves:

- blocking upstream stages run sequentially
- after itinerary is available, `Stay`, `Transport`, `Food`, and `Safety` are eligible for parallel fan-out
- `Budget`, `Review`, and `Governance` remain downstream fan-in stages

This gives the system lower wall-clock latency than a fully serialized specialist chain, without turning the runtime into uncontrolled agent chatter.

## Layer 4: Multi-Agent Execution Layer

This is where the specialist planning work happens.

Current agent roles:

- `Clarification`
- `Destination Research`
- `Itinerary`
- `Stay`
- `Transport`
- `Food`
- `Budget`
- `Safety`
- `Review`
- `Governance`

Main code:

- [backend/src/agents/travel_planner/multi_agent/adapters.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/agents/travel_planner/multi_agent/adapters.py:1)
- [backend/src/agents/travel_planner/nodes.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/agents/travel_planner/nodes.py:1)

Important nuance:

- the new runtime uses a coordinator-based agent model
- the actual specialist implementations still reuse the existing planner node logic underneath

So the system has a new multi-agent coordination model without throwing away the specialist planning logic that already existed.

## Layer 5: Tool and Provider Layer

This layer handles external information gathering and model-backed synthesis.

Main responsibilities:

- structured LLM calls
- web research
- weather lookup
- tool authorization and validation
- usage and audit tracking

Main code:

- [backend/src/agents/travel_planner/tooling/provider_tools.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/agents/travel_planner/tooling/provider_tools.py:1)
- [backend/src/agents/travel_planner/tooling/registry.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/agents/travel_planner/tooling/registry.py:1)
- [backend/src/agents/travel_planner/research_clients.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/agents/travel_planner/research_clients.py:1)

External providers:

- `OpenAI`
- `Tavily`
- `WeatherAPI`

Behavioral note:

- if a provider fails or times out, the planner can fall back to lower-confidence output instead of always crashing the whole run

## Layer 6: Runtime and Persistence Layer

This is the infrastructure layer that keeps the system durable and operable.

Main responsibilities:

- persist trips and workflow runs
- queue and execute async jobs
- store workflow step records
- maintain audit and observability data

Main code:

- [backend/src/services/workflow_runtime_service.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/services/workflow_runtime_service.py:1)
- [backend/src/bootstrap.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/bootstrap.py:1)

Backing systems:

- `Postgres`
  stores trips, workflow runs, workflow steps, and audit data
- `Redis`
  backs the queue and rate limiting
- `RQ worker`
  executes async planner runs

## Cross-Cutting Layers

Some concerns cut across every main layer.

### Security

Main responsibilities:

- API key validation
- actor id and actor role extraction
- role checks
- rate limiting

Main code:

- [backend/src/core/security.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/core/security.py:1)

### Audit and Observability

Main responsibilities:

- record audit events
- expose run traces and step traces
- support admin dashboards and alerts

Main code:

- [backend/src/services/audit_service.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/services/audit_service.py:1)
- [backend/src/services/observability_service.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/services/observability_service.py:1)
- [backend/src/services/operator_review_service.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/services/operator_review_service.py:1)

## End-to-End Flow

In practical terms, a normal async request flows like this:

1. The frontend sends a trip request to `POST /api/trips/async`.
2. FastAPI validates it and enqueues a workflow job.
3. The worker starts the coordinator runtime.
4. The coordinator dispatches upstream blocking work first.
5. Once itinerary exists, the runtime can fan out independent specialists in parallel.
6. Budget, review, and governance consume the completed artifacts.
7. The final trip, runtime, and trace data are saved and exposed back to the frontend.

## Current State

The current architecture is now best described as:

`React frontend -> FastAPI API -> LangGraph orchestrator -> Coordinator-driven multi-agent runtime -> specialist agents -> provider/tool layer -> Postgres/Redis/worker infrastructure`

That is more accurate than calling it only a fixed planner pipeline.
