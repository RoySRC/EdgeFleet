from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException

from edgefleet.actions import ActionRegistry
from edgefleet.llm import LLMBackend, ToolCall
from edgefleet.models import (
    AgentDescriptor,
    AgentRegistration,
    ApprovalRequest,
    HealthResponse,
    ReasoningConfig,
    ResumeRequest,
    SkillDescriptor,
    TaskRequest,
    TaskResult,
    TaskState,
)
from edgefleet.prompts import PromptBuilder, PromptTemplateRegistry
from edgefleet.reasoning import ReasoningEngine
from edgefleet.retrieval import Retriever
from edgefleet.security import BearerTokenAuth
from edgefleet.state import InMemoryRuntimeState, RuntimeStateStore
from edgefleet.version import __version__

SkillHandler = (
    Callable[[TaskRequest], Any]
    | Callable[[TaskRequest], Awaitable[Any]]
)
DelegationHandler = Callable[
    [str, str, TaskRequest], Awaitable[Any]
]


@dataclass(slots=True)
class SkillSpec:
    descriptor: SkillDescriptor
    handler: SkillHandler | None


class EdgeAgent:
    def __init__(
        self,
        *,
        agent_id: str,
        name: str,
        endpoint: str,
        description: str = "",
        llm: LLMBackend | None = None,
        system_prompt: str = "You are an edge agent. Be concise and safe.",
        actions: ActionRegistry | None = None,
        token: str | None = None,
        orchestrator_url: str | None = None,
        orchestrator_token: str | None = None,
        state: RuntimeStateStore | None = None,
        retriever: Retriever | None = None,
        delegation_handler: DelegationHandler | None = None,
        max_tool_rounds: int = 4,
    ) -> None:
        self.agent_id = agent_id
        self.name = name
        self.endpoint = endpoint.rstrip("/")
        self.description = description
        self.llm = llm
        self.system_prompt = system_prompt
        self.actions = actions or ActionRegistry()
        self.token = token
        self.orchestrator_url = orchestrator_url
        self.orchestrator_token = orchestrator_token
        self.state = state or InMemoryRuntimeState()
        self.retriever = retriever
        self.delegation_handler = delegation_handler
        self.max_tool_rounds = max_tool_rounds
        self.prompt_templates = PromptTemplateRegistry()
        self._skills: dict[str, SkillSpec] = {}

    def skill(
        self,
        name: str,
        *,
        description: str = "",
        tags: list[str] | None = None,
        input_schema: dict[str, Any] | None = None,
        prompt_template: str | None = None,
    ) -> Callable[[SkillHandler], SkillHandler]:
        def decorator(handler: SkillHandler) -> SkillHandler:
            if name in self._skills:
                raise ValueError(f"Skill already registered: {name}")
            descriptor = SkillDescriptor(
                name=name,
                description=description,
                tags=tags or [],
                input_schema=input_schema or {"type": "object"},
                prompt_template=prompt_template,
            )
            self._skills[name] = SkillSpec(descriptor, handler)
            if prompt_template:
                self.prompt_templates.register(name, prompt_template)
            return handler

        return decorator

    def prompt_skill(
        self,
        name: str,
        *,
        prompt_template: str,
        description: str = "",
        tags: list[str] | None = None,
        input_schema: dict[str, Any] | None = None,
    ) -> SkillDescriptor:
        if name in self._skills:
            raise ValueError(f"Skill already registered: {name}")
        descriptor = SkillDescriptor(
            name=name,
            description=description,
            tags=tags or ["llm"],
            input_schema=input_schema or {"type": "object"},
            prompt_template=prompt_template,
        )
        self._skills[name] = SkillSpec(descriptor, None)
        self.prompt_templates.register(name, prompt_template)
        return descriptor

    @property
    def descriptor(self) -> AgentDescriptor:
        skills = [item.descriptor for item in self._skills.values()]
        if self.llm is not None and not any(
            skill.name == "chat" for skill in skills
        ):
            skills.append(
                SkillDescriptor(
                    name="chat",
                    description="General local-LLM task execution",
                    tags=["llm"],
                )
            )
        return AgentDescriptor(
            id=self.agent_id,
            name=self.name,
            endpoint=self.endpoint,
            description=self.description,
            skills=skills,
        )

    async def execute(self, task: TaskRequest) -> TaskResult:
        started = datetime.now(UTC)
        result = TaskResult(
            task_id=task.id,
            state=TaskState.RUNNING,
            agent_id=self.agent_id,
            started_at=started,
        )
        try:
            skill = self._skills.get(task.skill) if task.skill else None
            if skill is not None and skill.handler is not None:
                handler = skill.handler
                output = handler(task)
                if inspect.isawaitable(output):
                    output = await output
                result.output = output
            elif self.llm is not None:
                outcome = await self._reasoning_engine().run(task)
                result.output = outcome.output
                result.trace = outcome.trace
                result.state = outcome.state
                result.pending_approvals = outcome.approvals
                result.pending_question = outcome.question
            else:
                requested = task.skill or "general task"
                raise LookupError(
                    f"Agent '{self.agent_id}' cannot execute {requested}"
                )
            if result.state is TaskState.RUNNING:
                result.state = TaskState.COMPLETED
        except Exception as exc:
            result.state = TaskState.FAILED
            result.error = f"{type(exc).__name__}: {exc}"
        result.finished_at = datetime.now(UTC)
        return result

    async def resume(
        self, task_id: str, request: ResumeRequest
    ) -> TaskResult:
        started = datetime.now(UTC)
        result = TaskResult(
            task_id=task_id,
            state=TaskState.RUNNING,
            agent_id=self.agent_id,
            started_at=started,
        )
        try:
            if self.llm is None:
                raise RuntimeError("Agent has no LLM runtime to resume")
            outcome = await self._reasoning_engine().resume(
                task_id,
                approved_actions=request.approved_actions,
                human_input=request.human_input,
            )
            result.output = outcome.output
            result.trace = outcome.trace
            result.state = outcome.state
            result.pending_approvals = outcome.approvals
            result.pending_question = outcome.question
        except Exception as exc:
            result.state = TaskState.FAILED
            result.error = f"{type(exc).__name__}: {exc}"
        result.finished_at = datetime.now(UTC)
        return result

    def _reasoning_engine(self) -> ReasoningEngine:
        if self.llm is None:
            raise RuntimeError("Agent has no LLM backend")
        return ReasoningEngine(
            llm=self.llm,
            prompt_builder=PromptBuilder(
                self.system_prompt, self.prompt_templates
            ),
            state=self.state,
            retriever=self.retriever,
            tool_provider=self._tool_provider,
            tool_executor=self._tool_executor,
            approval_checker=self._approval_checker,
            delegate=self._delegate_for_debate,
            max_tool_rounds=self.max_tool_rounds,
        )

    def _tool_provider(
        self, task: TaskRequest
    ) -> list[dict[str, Any]]:
        tools = self.actions.llm_tools()
        if task.reasoning.auto_delegate and (
            self.orchestrator_url or self.delegation_handler
        ):
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": "delegate_task",
                        "description": (
                            "Delegate a bounded subtask to another registered "
                            "edge agent."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "target_agent": {"type": "string"},
                                "skill": {"type": "string"},
                                "request": {"type": "string"},
                            },
                            "required": [
                                "target_agent",
                                "request",
                            ],
                            "additionalProperties": False,
                        },
                    },
                }
            )
        if task.reasoning.human_approval:
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": "request_human_input",
                        "description": (
                            "Pause and ask a human for a decision, missing "
                            "information, or explicit confirmation."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "string"}
                            },
                            "required": ["question"],
                            "additionalProperties": False,
                        },
                    },
                }
            )
        return tools

    def _approval_checker(
        self, call: ToolCall, task: TaskRequest
    ) -> ApprovalRequest | None:
        if call.name in {"delegate_task", "request_human_input"}:
            return None
        return self.actions.approval_requirement(
            call.name,
            call.arguments,
            task_id=task.id,
            allow_actions=task.allow_actions,
            approved_actions=task.approved_actions,
        )

    async def _tool_executor(
        self, call: ToolCall, task: TaskRequest
    ) -> Any:
        if call.name == "delegate_task":
            return await self._delegate_task(
                target_agent=call.arguments["target_agent"],
                skill=call.arguments.get("skill"),
                request=call.arguments["request"],
                parent=task,
            )
        if call.name == "request_human_input":
            raise RuntimeError(
                "Human-input calls must be handled as resumable pauses"
            )
        return await self.actions.execute(
            call.name,
            call.arguments,
            allow_actions=task.allow_actions,
            approved_actions=task.approved_actions,
        )

    async def _delegate_for_debate(
        self, agent_id: str, prompt: str, task: TaskRequest
    ) -> Any:
        return await self._delegate_task(
            target_agent=agent_id,
            skill="chat",
            request=prompt,
            parent=task,
        )

    async def _delegate_task(
        self,
        *,
        target_agent: str,
        skill: str | None,
        request: str,
        parent: TaskRequest,
    ) -> Any:
        if not self.orchestrator_url:
            if self.delegation_handler is None:
                raise RuntimeError("No orchestrator URL configured")
        depth = int(parent.context.get("delegation_depth", 0))
        visited = set(parent.context.get("visited_agents", []))
        if target_agent == self.agent_id or target_agent in visited:
            raise RuntimeError(
                f"Delegation cycle detected for agent: {target_agent}"
            )
        if depth >= parent.reasoning.max_delegation_depth:
            raise RuntimeError("Maximum delegation depth exceeded")
        if self.delegation_handler is not None:
            return await self.delegation_handler(
                target_agent, request, parent
            )

        from edgefleet.client import EdgeFleetClient

        client = EdgeFleetClient(
            self.orchestrator_url,
            token=self.orchestrator_token,
            timeout=parent.timeout_seconds,
        )
        child_reasoning = parent.reasoning.model_copy(
            update={
                "mode": "direct",
                "auto_delegate": False,
                "debate_agents": [],
            }
        )
        result = await client.submit(
            request,
            skill=skill,
            target_agent=target_agent,
            context={
                **parent.context,
                "delegation_depth": depth + 1,
                "visited_agents": sorted(visited | {self.agent_id}),
                "parent_task_id": parent.id,
            },
            metadata={"delegated_by": self.agent_id},
            reasoning=child_reasoning,
            conversation_id=parent.conversation_id,
        )
        if result.state is not TaskState.COMPLETED:
            raise RuntimeError(
                f"Delegated task failed with state={result.state}: "
                f"{result.error or result.pending_question}"
            )
        return result.output

    async def register_with(
        self,
        orchestrator_url: str,
        *,
        token: str | None = None,
    ) -> AgentDescriptor:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{orchestrator_url.rstrip('/')}/v1/agents/register",
                json=AgentRegistration(
                    agent=self.descriptor
                ).model_dump(mode="json"),
                headers=headers,
            )
            response.raise_for_status()
            return AgentDescriptor.model_validate(response.json())

    def create_app(self) -> FastAPI:
        auth = BearerTokenAuth(self.token)

        @asynccontextmanager
        async def lifespan(_: FastAPI):
            if self.orchestrator_url:
                await self.register_with(
                    self.orchestrator_url,
                    token=self.orchestrator_token,
                )
            yield

        app = FastAPI(
            title=f"EdgeFleet agent: {self.name}",
            version=__version__,
            lifespan=lifespan,
        )

        @app.get("/health", response_model=HealthResponse)
        async def health() -> HealthResponse:
            return HealthResponse(service=f"agent:{self.agent_id}")

        @app.get(
            "/.well-known/agent-card.json",
            response_model=AgentDescriptor,
        )
        async def agent_card() -> AgentDescriptor:
            return self.descriptor

        @app.post(
            "/v1/tasks",
            response_model=TaskResult,
            dependencies=[Depends(auth)],
        )
        async def submit_task(task: TaskRequest) -> TaskResult:
            result = await self.execute(task)
            if result.state is TaskState.REJECTED:
                raise HTTPException(status_code=403, detail=result.error)
            return result

        @app.post(
            "/v1/tasks/{task_id}/resume",
            response_model=TaskResult,
            dependencies=[Depends(auth)],
        )
        async def resume_task(
            task_id: str, request: ResumeRequest
        ) -> TaskResult:
            return await self.resume(task_id, request)

        return app
