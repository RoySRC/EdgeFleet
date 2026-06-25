from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from edgefleet.models import AgentDescriptor, TaskRequest


class Router(Protocol):
    async def select(
        self,
        task: TaskRequest,
        agents: Sequence[AgentDescriptor],
    ) -> AgentDescriptor:
        ...


class CapabilityRouter:
    """Deterministic router suitable for small edge fleets."""

    async def select(
        self,
        task: TaskRequest,
        agents: Sequence[AgentDescriptor],
    ) -> AgentDescriptor:
        candidates = list(agents)
        if task.target_agent:
            candidates = [
                agent for agent in candidates if agent.id == task.target_agent
            ]
        if task.skill:
            candidates = [
                agent for agent in candidates if agent.supports(task.skill)
            ]
        if not candidates:
            target = task.target_agent or task.skill or "any capability"
            raise LookupError(f"No online agent matches: {target}")
        return sorted(candidates, key=lambda item: item.id)[0]


class LangGraphRouter:
    """Adapter for a compiled LangGraph graph.

    The graph receives ``{"task": ..., "agents": ...}`` and must return an
    ``agent_id`` key. LangGraph stays optional and outside the core dependency
    set.
    """

    def __init__(self, graph: object) -> None:
        self.graph = graph

    async def select(
        self,
        task: TaskRequest,
        agents: Sequence[AgentDescriptor],
    ) -> AgentDescriptor:
        result = await self.graph.ainvoke(
            {
                "task": task.model_dump(mode="json"),
                "agents": [
                    agent.model_dump(mode="json") for agent in agents
                ],
            }
        )
        agent_id = result["agent_id"]
        for agent in agents:
            if agent.id == agent_id:
                return agent
        raise LookupError(f"LangGraph selected unknown agent: {agent_id}")
