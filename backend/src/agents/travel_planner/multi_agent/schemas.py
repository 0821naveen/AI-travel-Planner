from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentRole(str, Enum):
    COORDINATOR = "coordinator"
    CLARIFICATION = "clarification"
    DESTINATION_RESEARCH = "destination_research"
    ITINERARY = "itinerary"
    STAY = "stay"
    TRANSPORT = "transport"
    FOOD = "food"
    BUDGET = "budget"
    SAFETY = "safety"
    REVIEW = "review"
    GOVERNANCE = "governance"
    HUMAN_OPERATOR = "human_operator"


class AgentTaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    NEEDS_REVISION = "needs_revision"
    CANCELLED = "cancelled"


class MessageKind(str, Enum):
    TASK_ASSIGNMENT = "task_assignment"
    TASK_RESULT = "task_result"
    CRITIQUE = "critique"
    REVISION_REQUEST = "revision_request"
    CLARIFICATION_REQUEST = "clarification_request"
    STATUS_UPDATE = "status_update"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESULT = "approval_result"


class SharedObjective(BaseModel):
    trip_id: str
    user_goal: str
    success_criteria: list[str] = Field(default_factory=list)
    hard_constraints: list[str] = Field(default_factory=list)
    soft_preferences: list[str] = Field(default_factory=list)
    completion_definition: str


class DelegationDirective(BaseModel):
    from_role: AgentRole
    to_role: AgentRole
    reason: str
    expected_artifact_key: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    max_revision_rounds: int = Field(default=1, ge=0, le=3)


class RevisionRequest(BaseModel):
    target_role: AgentRole
    reason: str
    required_changes: list[str] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)


class AgentTask(BaseModel):
    task_id: str
    title: str
    owner_role: AgentRole
    goal: str
    status: AgentTaskStatus = AgentTaskStatus.PENDING
    deliverable_key: str
    depends_on: list[str] = Field(default_factory=list)
    allowed_delegate_roles: list[AgentRole] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    context_keys: list[str] = Field(default_factory=list)
    revision_count: int = Field(default=0, ge=0)
    max_revision_rounds: int = Field(default=1, ge=0, le=3)


class AgentMessage(BaseModel):
    message_id: str
    kind: MessageKind
    sender_role: AgentRole
    recipient_role: AgentRole
    task_id: Optional[str] = None
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    artifact_keys: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    requires_response: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CoordinationLedger(BaseModel):
    objective: SharedObjective
    active_role: AgentRole = AgentRole.COORDINATOR
    task_board: list[AgentTask] = Field(default_factory=list)
    message_log: list[AgentMessage] = Field(default_factory=list)
    artifacts: dict[str, dict[str, Any]] = Field(default_factory=dict)
    open_questions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    governance_flags: list[str] = Field(default_factory=list)
    iteration_count: int = Field(default=0, ge=0)
    max_iterations: int = Field(default=20, ge=1, le=40)
