from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable
from pathlib import Path

from edgefleet.models import AgentDescriptor, Goal, TaskResult


class InMemoryStore:
    """Concurrency-safe development store.

    Replace this with a database-backed implementation before running more
    than one orchestrator replica.
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentDescriptor] = {}
        self._tasks: dict[str, TaskResult] = {}
        self._goals: dict[str, Goal] = {}
        self._lock = asyncio.Lock()

    async def put_agent(self, agent: AgentDescriptor) -> AgentDescriptor:
        async with self._lock:
            self._agents[agent.id] = agent
        return agent

    async def get_agent(self, agent_id: str) -> AgentDescriptor | None:
        async with self._lock:
            return self._agents.get(agent_id)

    async def list_agents(self) -> list[AgentDescriptor]:
        async with self._lock:
            return list(self._agents.values())

    async def put_task(self, task: TaskResult) -> TaskResult:
        async with self._lock:
            self._tasks[task.task_id] = task
        return task

    async def get_task(self, task_id: str) -> TaskResult | None:
        async with self._lock:
            return self._tasks.get(task_id)

    async def list_tasks(self) -> Iterable[TaskResult]:
        async with self._lock:
            return list(self._tasks.values())

    async def put_goal(self, goal: Goal) -> Goal:
        async with self._lock:
            self._goals[goal.id] = goal
        return goal

    async def get_goal(self, goal_id: str) -> Goal | None:
        async with self._lock:
            return self._goals.get(goal_id)

    async def list_goals(self) -> list[Goal]:
        async with self._lock:
            return list(self._goals.values())


class JsonFileStore(InMemoryStore):
    """Persistent single-process orchestrator store."""

    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self.path = Path(path)
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        async with self._lock:
            if self._loaded:
                return
            if self.path.exists():
                raw = json.loads(self.path.read_text())
                self._agents = {
                    key: AgentDescriptor.model_validate(value)
                    for key, value in raw.get("agents", {}).items()
                }
                self._tasks = {
                    key: TaskResult.model_validate(value)
                    for key, value in raw.get("tasks", {}).items()
                }
                self._goals = {
                    key: Goal.model_validate(value)
                    for key, value in raw.get("goals", {}).items()
                }
            self._loaded = True

    async def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "agents": {
                key: value.model_dump(mode="json")
                for key, value in self._agents.items()
            },
            "tasks": {
                key: value.model_dump(mode="json")
                for key, value in self._tasks.items()
            },
            "goals": {
                key: value.model_dump(mode="json")
                for key, value in self._goals.items()
            },
        }
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(json.dumps(payload, indent=2))
        temporary.replace(self.path)

    async def put_agent(self, agent: AgentDescriptor) -> AgentDescriptor:
        await self._ensure_loaded()
        async with self._lock:
            self._agents[agent.id] = agent
            await self._persist()
        return agent

    async def get_agent(self, agent_id: str) -> AgentDescriptor | None:
        await self._ensure_loaded()
        return await super().get_agent(agent_id)

    async def list_agents(self) -> list[AgentDescriptor]:
        await self._ensure_loaded()
        return await super().list_agents()

    async def put_task(self, task: TaskResult) -> TaskResult:
        await self._ensure_loaded()
        async with self._lock:
            self._tasks[task.task_id] = task
            await self._persist()
        return task

    async def get_task(self, task_id: str) -> TaskResult | None:
        await self._ensure_loaded()
        return await super().get_task(task_id)

    async def list_tasks(self) -> Iterable[TaskResult]:
        await self._ensure_loaded()
        return await super().list_tasks()

    async def put_goal(self, goal: Goal) -> Goal:
        await self._ensure_loaded()
        async with self._lock:
            self._goals[goal.id] = goal
            await self._persist()
        return goal

    async def get_goal(self, goal_id: str) -> Goal | None:
        await self._ensure_loaded()
        return await super().get_goal(goal_id)

    async def list_goals(self) -> list[Goal]:
        await self._ensure_loaded()
        return await super().list_goals()
