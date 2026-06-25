from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from edgefleet.models import ConversationMessage, TaskRequest


class ExecutionCheckpoint(BaseModel):
    task: TaskRequest
    messages: list[dict[str, Any]]
    trace: list[dict[str, Any]] = Field(default_factory=list)
    pending_tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    assistant_message: dict[str, Any] | None = None
    kind: str
    question: str | None = None
    human_input: str | None = None


class RuntimeStateStore(ABC):
    @abstractmethod
    async def save_checkpoint(
        self, task_id: str, checkpoint: ExecutionCheckpoint
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_checkpoint(
        self, task_id: str
    ) -> ExecutionCheckpoint | None:
        raise NotImplementedError

    @abstractmethod
    async def delete_checkpoint(self, task_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def append_memory(
        self, conversation_id: str, message: ConversationMessage
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_memory(
        self, conversation_id: str, limit: int = 20
    ) -> list[ConversationMessage]:
        raise NotImplementedError


class InMemoryRuntimeState(RuntimeStateStore):
    def __init__(self) -> None:
        self._checkpoints: dict[str, ExecutionCheckpoint] = {}
        self._memory: dict[str, list[ConversationMessage]] = {}
        self._lock = asyncio.Lock()

    async def save_checkpoint(
        self, task_id: str, checkpoint: ExecutionCheckpoint
    ) -> None:
        async with self._lock:
            self._checkpoints[task_id] = checkpoint

    async def get_checkpoint(
        self, task_id: str
    ) -> ExecutionCheckpoint | None:
        async with self._lock:
            return self._checkpoints.get(task_id)

    async def delete_checkpoint(self, task_id: str) -> None:
        async with self._lock:
            self._checkpoints.pop(task_id, None)

    async def append_memory(
        self, conversation_id: str, message: ConversationMessage
    ) -> None:
        async with self._lock:
            self._memory.setdefault(conversation_id, []).append(message)

    async def get_memory(
        self, conversation_id: str, limit: int = 20
    ) -> list[ConversationMessage]:
        async with self._lock:
            return list(self._memory.get(conversation_id, [])[-limit:])


class JsonFileRuntimeState(InMemoryRuntimeState):
    """Small persistent runtime store for one edge-agent process.

    It uses atomic file replacement and is not intended for concurrent writers
    from multiple processes.
    """

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
                self._checkpoints = {
                    key: ExecutionCheckpoint.model_validate(value)
                    for key, value in raw.get("checkpoints", {}).items()
                }
                self._memory = {
                    key: [
                        ConversationMessage.model_validate(item)
                        for item in values
                    ]
                    for key, values in raw.get("memory", {}).items()
                }
            self._loaded = True

    async def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "checkpoints": {
                key: value.model_dump(mode="json")
                for key, value in self._checkpoints.items()
            },
            "memory": {
                key: [
                    value.model_dump(mode="json") for value in values
                ]
                for key, values in self._memory.items()
            },
        }
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(json.dumps(payload, indent=2))
        temporary.replace(self.path)

    async def save_checkpoint(
        self, task_id: str, checkpoint: ExecutionCheckpoint
    ) -> None:
        await self._ensure_loaded()
        async with self._lock:
            self._checkpoints[task_id] = checkpoint
            await self._persist()

    async def get_checkpoint(
        self, task_id: str
    ) -> ExecutionCheckpoint | None:
        await self._ensure_loaded()
        return await super().get_checkpoint(task_id)

    async def delete_checkpoint(self, task_id: str) -> None:
        await self._ensure_loaded()
        async with self._lock:
            self._checkpoints.pop(task_id, None)
            await self._persist()

    async def append_memory(
        self, conversation_id: str, message: ConversationMessage
    ) -> None:
        await self._ensure_loaded()
        async with self._lock:
            self._memory.setdefault(conversation_id, []).append(message)
            await self._persist()

    async def get_memory(
        self, conversation_id: str, limit: int = 20
    ) -> list[ConversationMessage]:
        await self._ensure_loaded()
        return await super().get_memory(conversation_id, limit)
