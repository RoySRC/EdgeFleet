from __future__ import annotations

from collections.abc import Awaitable, Callable

from edgefleet.models import TaskRequest, TaskResult


class NATSTaskTransport:
    """NATS request/reply transport for networks where direct HTTP is awkward."""

    def __init__(
        self,
        servers: list[str] | None = None,
        *,
        subject_prefix: str = "edgefleet.tasks",
    ) -> None:
        self.servers = servers or ["nats://127.0.0.1:4222"]
        self.subject_prefix = subject_prefix
        self._client = None
        self._subscriptions = []

    async def connect(self) -> None:
        try:
            import nats
        except ImportError as exc:
            raise RuntimeError(
                "Install EdgeFleet with the NATS extra: pip install "
                "'edgefleet[nats]'"
            ) from exc
        self._client = await nats.connect(servers=self.servers)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.drain()
            self._client = None

    async def request(
        self,
        agent_id: str,
        task: TaskRequest,
    ) -> TaskResult:
        if self._client is None:
            raise RuntimeError("NATS transport is not connected")
        message = await self._client.request(
            f"{self.subject_prefix}.{agent_id}",
            task.model_dump_json().encode(),
            timeout=task.timeout_seconds,
        )
        return TaskResult.model_validate_json(message.data)

    async def serve(
        self,
        agent_id: str,
        handler: Callable[[TaskRequest], Awaitable[TaskResult]],
    ) -> None:
        if self._client is None:
            raise RuntimeError("NATS transport is not connected")

        async def callback(message: object) -> None:
            task = TaskRequest.model_validate_json(message.data)
            result = await handler(task)
            await message.respond(result.model_dump_json().encode())

        subscription = await self._client.subscribe(
            f"{self.subject_prefix}.{agent_id}",
            cb=callback,
        )
        self._subscriptions.append(subscription)

