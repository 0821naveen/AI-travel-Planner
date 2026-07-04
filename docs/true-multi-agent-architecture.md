# Target True Multi-Agent Architecture

This document describes the target architecture if the current planner is upgraded from a sequential `LangGraph` pipeline into a true autonomous multi-agent system.

It is intentionally grounded in the current codebase rather than a greenfield design.

## Why The Current Design Is Not Yet True Multi-Agent

Today the backend planner is orchestrated in [backend/src/agents/travel_planner/graph.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/agents/travel_planner/graph.py:1) as a fixed chain of bounded nodes.

Key limits of the current design:

- one shared `PlannerContext`
- fixed sequential execution after clarification
- no task delegation between specialists
- no revision loop driven by critiques
- no agent-owned working memory
- no coordinator that can re-plan mid-run

That is a solid workflow pipeline, but not a true autonomous multi-agent system.

## Target Runtime Shape

The target runtime keeps `FastAPI`, `Postgres`, `Redis`, and `LangGraph`, but changes how orchestration works.

High-level target:

```text
React Frontend
  -> FastAPI API
     -> Multi-Agent Runtime
        -> Coordinator Agent
           -> Specialist Agents
           -> Reviewer Agent
           -> Governance Agent
           -> Human Operator Escalation
     -> Postgres + Redis + Audit Trail
```

## Agent Roles

The first concrete role definitions now live in:

- [backend/src/agents/travel_planner/multi_agent/schemas.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/agents/travel_planner/multi_agent/schemas.py:1)
- [backend/src/agents/travel_planner/multi_agent/topology.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/agents/travel_planner/multi_agent/topology.py:1)

Target roles:

- `Coordinator`
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
- `Human Operator`

## Core Operating Model

The coordinator owns the top-level objective and chooses which specialist acts next.

Specialists do not execute in a hardcoded linear sequence. They operate by:

1. receiving a typed task assignment
2. producing a typed artifact
3. declaring confidence, issues, and open gaps
4. optionally receiving a revision request
5. stopping when their contract is satisfied

The reviewer and governance agents are not just terminal display steps. They can force rework.

## Required State Shift

The current state model in [backend/src/agents/travel_planner/state.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/agents/travel_planner/state.py:1) is optimized for a single shared-state workflow.

The target system needs a coordination ledger with:

- shared objective
- task board
- message log
- artifact store
- open questions
- risk register
- governance flags
- bounded iteration counters

That first version is now modeled as `CoordinationLedger` in [multi_agent/schemas.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/agents/travel_planner/multi_agent/schemas.py:86).

## Required Communication Shift

Instead of agents only reading and mutating global fields, they should exchange typed messages:

- `TASK_ASSIGNMENT`
- `TASK_RESULT`
- `CRITIQUE`
- `REVISION_REQUEST`
- `CLARIFICATION_REQUEST`
- `APPROVAL_REQUEST`
- `APPROVAL_RESULT`

Those message types are now modeled in [multi_agent/schemas.py](/Users/naveen.kumar.p/Desktop/pprojects/travel-planner-agent/backend/src/agents/travel_planner/multi_agent/schemas.py:27).

## Delegation Rules

The critical rule is controlled delegation, not free-for-all delegation.

Examples from the topology:

- `Coordinator` may delegate to any specialist
- `Budget` may request revisions from `Itinerary`, `Stay`, `Transport`, or `Food`
- `Review` may request targeted revisions from producing specialists
- `Food` may not delegate to `Governance`

This prevents uncontrolled recursive chatter.

## Suggested Runtime Loop

The future orchestrator should work like this:

1. Coordinator creates the initial task board
2. Clarification agent decides whether the request is blocking or non-blocking
3. Coordinator dispatches the next specialist based on missing artifacts
4. Specialist writes a typed artifact and confidence signal
5. Reviewer or budget agent may request revisions
6. Coordinator either reassigns work or advances the plan
7. Governance either approves or escalates to a human

That is the minimum viable autonomous loop for this repo.

## Migration Plan

### Phase 1

Land coordination contracts without changing runtime behavior.

Deliverables:

- typed agent roles
- typed task board
- typed message log
- explicit delegation matrix

Status:

- done in `backend/src/agents/travel_planner/multi_agent/`

### Phase 2

Introduce a coordinator-driven runtime beside the current `TravelPlannerGraph`.

Deliverables:

- `CoordinatorRuntime`
- conversion from `TripRequest` to `CoordinationLedger`
- specialist adapters that wrap current nodes
- iteration guardrails

### Phase 3

Move existing node implementations behind specialist-agent interfaces.

Deliverables:

- `ResearchAgentAdapter`
- `ItineraryAgentAdapter`
- `BudgetAgentAdapter`
- `ReviewAgentAdapter`
- revision handling and critique loops

### Phase 4

Persist coordination state and agent messages as first-class runtime records.

Deliverables:

- DB tables for agent tasks and agent messages
- API endpoints for coordination traces
- frontend panels for agent-level reasoning and rework loops

### Phase 5

Allow bounded autonomy with operator escalation.

Deliverables:

- approval checkpoints
- human review interrupts
- task replay and recovery
- stronger governance policies

## Recommended Folder Shape

The next backend layout should move toward:

```text
backend/src/agents/travel_planner/
  graph.py                        # current pipeline runtime
  multi_agent/
    schemas.py                    # roles, tasks, messages, ledger
    topology.py                   # delegation rules and role specs
    runtime.py                    # future coordinator loop
    adapters.py                   # wrappers around current specialist nodes
    prompts/
      coordinator.py
      reviewer.py
      specialists.py
```

## What Should Stay

These existing repo choices still fit the target architecture:

- `FastAPI`
- `LangGraph`
- `Redis` worker execution
- `Postgres` persistence
- tool registry and tool authorization
- review and audit services

The problem is not the infrastructure. The problem is the current coordination model.

## Immediate Next Refactor

The next implementation step should be:

1. add `multi_agent/runtime.py`
2. build a coordinator loop around `CoordinationLedger`
3. wrap current specialist nodes as adapter-backed specialists
4. route budget and review findings into revision tasks instead of terminal notes

That is the point where this repo starts behaving like a true multi-agent system instead of a staged planner pipeline.
