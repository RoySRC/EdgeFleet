from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from edgefleet.version import __version__


def utc_now() -> datetime:
    return datetime.now(UTC)


class TaskState(StrEnum):
    SUBMITTED = "submitted"
    ROUTING = "routing"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_INPUT = "waiting_input"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class ReasoningMode(StrEnum):
    DIRECT = "direct"
    PLAN_EXECUTE = "plan_execute"
    SELF_CONSISTENCY = "self_consistency"
    TREE_SEARCH = "tree_search"
    GRAPH_SEARCH = "graph_search"
    DEBATE = "debate"


class ReasoningConfig(BaseModel):
    mode: ReasoningMode = ReasoningMode.DIRECT
    reflection: bool = False
    reasoning_summary: bool = False
    samples: int = Field(default=3, ge=2, le=8)
    branches: int = Field(default=3, ge=2, le=8)
    depth: int = Field(default=2, ge=1, le=5)
    debate_rounds: int = Field(default=2, ge=1, le=5)
    debate_agents: list[str] = Field(default_factory=list)
    memory: bool = False
    retrieval: bool = False
    retrieval_limit: int = Field(default=4, ge=1, le=20)
    auto_delegate: bool = False
    max_delegation_depth: int = Field(default=2, ge=0, le=8)
    human_approval: bool = False


class SkillDescriptor(BaseModel):
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object"}
    )
    prompt_template: str | None = None


class AgentDescriptor(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    endpoint: HttpUrl
    description: str = ""
    version: str = __version__
    skills: list[SkillDescriptor] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    last_seen: datetime = Field(default_factory=utc_now)

    def supports(self, skill: str | None) -> bool:
        if skill is None:
            return True
        return any(item.name == skill for item in self.skills)


class TaskRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    input: Any
    skill: str | None = None
    target_agent: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    conversation_id: str | None = None
    goal_id: str | None = None
    reasoning: ReasoningConfig = Field(default_factory=ReasoningConfig)
    allow_actions: bool = False
    approved_actions: set[str] = Field(default_factory=set)
    timeout_seconds: float = Field(default=120.0, gt=0, le=3600)


class TaskResult(BaseModel):
    task_id: str
    state: TaskState
    output: Any = None
    error: str | None = None
    agent_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    trace: list[dict[str, Any]] = Field(default_factory=list)
    pending_approvals: list["ApprovalRequest"] = Field(default_factory=list)
    pending_question: str | None = None


class ApprovalRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    action: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    policy: str
    prompt: str


class ResumeRequest(BaseModel):
    approved_actions: set[str] = Field(default_factory=set)
    human_input: str | None = None


class ConversationMessage(BaseModel):
    role: str
    content: Any
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class GoalState(StrEnum):
    ACTIVE = "active"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_INPUT = "waiting_input"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class Goal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    objective: str
    task: TaskRequest
    state: GoalState = GoalState.ACTIVE
    attempts: int = 0
    current_task_id: str | None = None
    result: TaskResult | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class GoalRequest(BaseModel):
    objective: str
    task: TaskRequest


class AgentRegistration(BaseModel):
    agent: AgentDescriptor


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
    version: str = __version__
