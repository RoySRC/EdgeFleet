from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from edgefleet.agent import EdgeAgent
from edgefleet.models import TaskRequest, TaskState as EdgeTaskState


def mount_a2a(
    app: FastAPI,
    agent: EdgeAgent,
    *,
    rpc_path: str = "/a2a",
    card_path: str = "/.well-known/a2a-agent-card.json",
) -> None:
    """Mount an official A2A Protocol 1.0 JSON-RPC facade.

    Text input is mapped to an EdgeFleet task. Optional A2A message metadata
    can contain ``skill``, ``allow_actions``, and ``approved_actions``.
    """

    try:
        from a2a.helpers import new_data_message, new_text_message
        from a2a.server.agent_execution import AgentExecutor
        from a2a.server.request_handlers import DefaultRequestHandler
        from a2a.server.routes import (
            add_a2a_routes_to_fastapi,
            create_agent_card_routes,
            create_jsonrpc_routes,
        )
        from a2a.server.tasks import InMemoryTaskStore
        from a2a.types import (
            AgentCapabilities,
            AgentCard,
            AgentInterface,
            AgentSkill,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Install EdgeFleet with the A2A extra: pip install "
            "'edgefleet[a2a]'"
        ) from exc

    class EdgeFleetA2AExecutor(AgentExecutor):
        async def execute(self, context: Any, event_queue: Any) -> None:
            metadata = context.metadata
            task = TaskRequest(
                input=context.get_user_input(),
                skill=metadata.get("skill"),
                context={"a2a_context_id": context.context_id},
                metadata=metadata,
                allow_actions=bool(metadata.get("allow_actions", False)),
                approved_actions=set(
                    metadata.get("approved_actions", [])
                ),
            )
            result = await agent.execute(task)
            message_kwargs = {
                "context_id": context.context_id,
                "task_id": context.task_id,
            }
            if result.state is EdgeTaskState.COMPLETED:
                event = new_data_message(
                    result.output,
                    **message_kwargs,
                )
            else:
                event = new_text_message(
                    result.error or "EdgeFleet task failed",
                    **message_kwargs,
                )
            await event_queue.enqueue_event(event)

        async def cancel(self, context: Any, event_queue: Any) -> None:
            await event_queue.enqueue_event(
                new_text_message(
                    "This EdgeFleet agent uses immediate A2A responses; "
                    "there is no running task to cancel.",
                    context_id=context.context_id,
                    task_id=context.task_id,
                )
            )

    descriptor = agent.descriptor
    skills = [
        AgentSkill(
            id=skill.name,
            name=skill.name,
            description=skill.description or skill.name,
            tags=skill.tags,
            input_modes=["text/plain", "application/json"],
            output_modes=["text/plain", "application/json"],
        )
        for skill in descriptor.skills
    ]
    card = AgentCard(
        name=descriptor.name,
        description=descriptor.description or descriptor.name,
        supported_interfaces=[
            AgentInterface(
                url=f"{str(descriptor.endpoint).rstrip('/')}{rpc_path}",
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            )
        ],
        version=descriptor.version,
        capabilities=AgentCapabilities(
            streaming=False,
            push_notifications=False,
        ),
        default_input_modes=["text/plain", "application/json"],
        default_output_modes=["text/plain", "application/json"],
        skills=skills,
    )
    handler = DefaultRequestHandler(
        agent_executor=EdgeFleetA2AExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(
            card, card_url=card_path
        ),
        jsonrpc_routes=create_jsonrpc_routes(
            handler, rpc_url=rpc_path
        ),
    )

