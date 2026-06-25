from __future__ import annotations

from typing import Any

import httpx

from edgefleet.models import (
    AgentDescriptor,
    Goal,
    GoalRequest,
    ReasoningConfig,
    ResumeRequest,
    TaskRequest,
    TaskResult,
)


class EdgeFleetClient:
    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        timeout: float = 120,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    async def submit(
        self,
        input: Any,
        *,
        skill: str | None = None,
        target_agent: str | None = None,
        allow_actions: bool = False,
        approved_actions: set[str] | None = None,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        reasoning: ReasoningConfig | None = None,
        conversation_id: str | None = None,
        goal_id: str | None = None,
    ) -> TaskResult:
        task = TaskRequest(
            input=input,
            skill=skill,
            target_agent=target_agent,
            allow_actions=allow_actions,
            approved_actions=approved_actions or set(),
            context=context or {},
            metadata=metadata or {},
            reasoning=reasoning or ReasoningConfig(),
            conversation_id=conversation_id,
            goal_id=goal_id,
            timeout_seconds=self.timeout,
        )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/v1/tasks",
                json=task.model_dump(mode="json"),
                headers=self._headers,
            )
            response.raise_for_status()
            return TaskResult.model_validate(response.json())

    async def resume(
        self,
        task_id: str,
        *,
        approved_actions: set[str] | None = None,
        human_input: str | None = None,
    ) -> TaskResult:
        request = ResumeRequest(
            approved_actions=approved_actions or set(),
            human_input=human_input,
        )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/v1/tasks/{task_id}/resume",
                json=request.model_dump(mode="json"),
                headers=self._headers,
            )
            response.raise_for_status()
            return TaskResult.model_validate(response.json())

    async def create_goal(
        self, objective: str, task: TaskRequest
    ) -> Goal:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/v1/goals",
                json=GoalRequest(
                    objective=objective, task=task
                ).model_dump(mode="json"),
                headers=self._headers,
            )
            response.raise_for_status()
            return Goal.model_validate(response.json())

    async def goal(self, goal_id: str) -> Goal:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/v1/goals/{goal_id}",
                headers=self._headers,
            )
            response.raise_for_status()
            return Goal.model_validate(response.json())

    async def resume_goal(
        self,
        goal_id: str,
        *,
        approved_actions: set[str] | None = None,
        human_input: str | None = None,
    ) -> Goal:
        request = ResumeRequest(
            approved_actions=approved_actions or set(),
            human_input=human_input,
        )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/v1/goals/{goal_id}/resume",
                json=request.model_dump(mode="json"),
                headers=self._headers,
            )
            response.raise_for_status()
            return Goal.model_validate(response.json())

    async def agents(self) -> list[AgentDescriptor]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/v1/agents",
                headers=self._headers,
            )
            response.raise_for_status()
            return [
                AgentDescriptor.model_validate(item)
                for item in response.json()
            ]

    async def task(self, task_id: str) -> TaskResult:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/v1/tasks/{task_id}",
                headers=self._headers,
            )
            response.raise_for_status()
            return TaskResult.model_validate(response.json())
