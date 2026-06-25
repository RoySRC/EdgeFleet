from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
from fastapi import Depends, FastAPI, HTTPException, status

from edgefleet.agent import EdgeAgent
from edgefleet.models import (
    AgentDescriptor,
    AgentRegistration,
    Goal,
    GoalRequest,
    GoalState,
    HealthResponse,
    ResumeRequest,
    TaskRequest,
    TaskResult,
    TaskState,
    utc_now,
)
from edgefleet.routing import CapabilityRouter, Router
from edgefleet.security import BearerTokenAuth
from edgefleet.store import InMemoryStore
from edgefleet.version import __version__


class Orchestrator:
    def __init__(
        self,
        *,
        store: InMemoryStore | None = None,
        router: Router | None = None,
        token: str | None = None,
        edge_token: str | None = None,
        local_agents: list[EdgeAgent] | None = None,
    ) -> None:
        self.store = store or InMemoryStore()
        self.router = router or CapabilityRouter()
        self.token = token
        self.edge_token = edge_token
        self.local_agents = {
            agent.agent_id: agent for agent in (local_agents or [])
        }

    async def register(self, agent: AgentDescriptor) -> AgentDescriptor:
        agent.last_seen = datetime.now(UTC)
        return await self.store.put_agent(agent)

    async def submit(self, task: TaskRequest) -> TaskResult:
        pending = TaskResult(
            task_id=task.id,
            state=TaskState.ROUTING,
        )
        await self.store.put_task(pending)

        try:
            agents = await self.store.list_agents()
            agent = await self.router.select(task, agents)
            if agent.id in self.local_agents:
                result = await self.local_agents[agent.id].execute(task)
            else:
                result = await self._dispatch_remote(agent, task)
        except Exception as exc:
            result = TaskResult(
                task_id=task.id,
                state=TaskState.FAILED,
                error=f"{type(exc).__name__}: {exc}",
            )

        await self.store.put_task(result)
        return result

    async def _dispatch_remote(
        self,
        agent: AgentDescriptor,
        task: TaskRequest,
    ) -> TaskResult:
        headers = {}
        if self.edge_token:
            headers["Authorization"] = f"Bearer {self.edge_token}"
        timeout = httpx.Timeout(task.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{str(agent.endpoint).rstrip('/')}/v1/tasks",
                json=task.model_dump(mode="json"),
                headers=headers,
            )
            response.raise_for_status()
            return TaskResult.model_validate(response.json())

    async def resume(
        self, task_id: str, request: ResumeRequest
    ) -> TaskResult:
        existing = await self.store.get_task(task_id)
        if existing is None:
            raise LookupError(f"Task not found: {task_id}")
        if not existing.agent_id:
            raise RuntimeError("Task has no assigned agent")
        if existing.agent_id in self.local_agents:
            result = await self.local_agents[existing.agent_id].resume(
                task_id, request
            )
        else:
            agent = await self.store.get_agent(existing.agent_id)
            if agent is None:
                raise LookupError(
                    f"Agent not found: {existing.agent_id}"
                )
            headers = {}
            if self.edge_token:
                headers["Authorization"] = (
                    f"Bearer {self.edge_token}"
                )
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{str(agent.endpoint).rstrip('/')}"
                    f"/v1/tasks/{task_id}/resume",
                    json=request.model_dump(mode="json"),
                    headers=headers,
                )
                response.raise_for_status()
                result = TaskResult.model_validate(response.json())
        await self.store.put_task(result)
        return result

    async def create_goal(self, request: GoalRequest) -> Goal:
        goal = Goal(objective=request.objective, task=request.task)
        goal.task.goal_id = goal.id
        await self.store.put_goal(goal)
        return await self._run_goal(goal)

    async def _run_goal(self, goal: Goal) -> Goal:
        goal.attempts += 1
        goal.updated_at = utc_now()
        result = await self.submit(goal.task)
        goal.current_task_id = result.task_id
        goal.result = result
        goal.state = self._goal_state(result.state)
        goal.updated_at = utc_now()
        return await self.store.put_goal(goal)

    async def resume_goal(
        self, goal_id: str, request: ResumeRequest
    ) -> Goal:
        goal = await self.store.get_goal(goal_id)
        if goal is None:
            raise LookupError(f"Goal not found: {goal_id}")
        if goal.current_task_id is None:
            return await self._run_goal(goal)
        goal.attempts += 1
        result = await self.resume(goal.current_task_id, request)
        goal.result = result
        goal.state = self._goal_state(result.state)
        goal.updated_at = utc_now()
        return await self.store.put_goal(goal)

    @staticmethod
    def _goal_state(state: TaskState) -> GoalState:
        mapping = {
            TaskState.WAITING_APPROVAL: GoalState.WAITING_APPROVAL,
            TaskState.WAITING_INPUT: GoalState.WAITING_INPUT,
            TaskState.PAUSED: GoalState.PAUSED,
            TaskState.COMPLETED: GoalState.COMPLETED,
            TaskState.FAILED: GoalState.FAILED,
            TaskState.REJECTED: GoalState.FAILED,
        }
        return mapping.get(state, GoalState.ACTIVE)

    async def initialize(self) -> None:
        for agent in self.local_agents.values():
            await self.register(agent.descriptor)

    def create_app(self) -> FastAPI:
        auth = BearerTokenAuth(self.token)

        @asynccontextmanager
        async def lifespan(_: FastAPI):
            await self.initialize()
            yield

        app = FastAPI(
            title="EdgeFleet orchestrator",
            version=__version__,
            lifespan=lifespan,
        )

        @app.get("/health", response_model=HealthResponse)
        async def health() -> HealthResponse:
            return HealthResponse(service="orchestrator")

        @app.post(
            "/v1/agents/register",
            response_model=AgentDescriptor,
            dependencies=[Depends(auth)],
        )
        async def register_agent(
            request: AgentRegistration,
        ) -> AgentDescriptor:
            return await self.register(request.agent)

        @app.get(
            "/v1/agents",
            response_model=list[AgentDescriptor],
            dependencies=[Depends(auth)],
        )
        async def list_agents() -> list[AgentDescriptor]:
            return await self.store.list_agents()

        @app.post(
            "/v1/tasks",
            response_model=TaskResult,
            dependencies=[Depends(auth)],
        )
        async def submit_task(task: TaskRequest) -> TaskResult:
            return await self.submit(task)

        @app.get(
            "/v1/tasks/{task_id}",
            response_model=TaskResult,
            dependencies=[Depends(auth)],
        )
        async def get_task(task_id: str) -> TaskResult:
            result = await self.store.get_task(task_id)
            if result is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Task not found",
                )
            return result

        @app.post(
            "/v1/tasks/{task_id}/resume",
            response_model=TaskResult,
            dependencies=[Depends(auth)],
        )
        async def resume_task(
            task_id: str, request: ResumeRequest
        ) -> TaskResult:
            try:
                return await self.resume(task_id, request)
            except LookupError as exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(exc),
                ) from exc

        @app.post(
            "/v1/goals",
            response_model=Goal,
            dependencies=[Depends(auth)],
        )
        async def create_goal(request: GoalRequest) -> Goal:
            return await self.create_goal(request)

        @app.get(
            "/v1/goals",
            response_model=list[Goal],
            dependencies=[Depends(auth)],
        )
        async def list_goals() -> list[Goal]:
            return await self.store.list_goals()

        @app.get(
            "/v1/goals/{goal_id}",
            response_model=Goal,
            dependencies=[Depends(auth)],
        )
        async def get_goal(goal_id: str) -> Goal:
            goal = await self.store.get_goal(goal_id)
            if goal is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Goal not found",
                )
            return goal

        @app.post(
            "/v1/goals/{goal_id}/resume",
            response_model=Goal,
            dependencies=[Depends(auth)],
        )
        async def resume_goal(
            goal_id: str, request: ResumeRequest
        ) -> Goal:
            try:
                return await self.resume_goal(goal_id, request)
            except LookupError as exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(exc),
                ) from exc

        return app
