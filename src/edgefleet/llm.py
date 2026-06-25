from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class LLMResponse:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


class LLMBackend(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        raise NotImplementedError


class OpenAICompatibleLLM(LLMBackend):
    """Adapter for llama.cpp, Ollama, vLLM, and compatible servers."""

    def __init__(
        self,
        *,
        model: str,
        base_url: str = "http://127.0.0.1:8080/v1",
        api_key: str = "local",
        timeout: float = 120,
        temperature: float = 0.1,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.temperature = temperature

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        message = data["choices"][0]["message"]
        tool_calls = []
        for item in message.get("tool_calls") or []:
            arguments = item["function"].get("arguments", {})
            if isinstance(arguments, str):
                import json

                arguments = json.loads(arguments)
            tool_calls.append(
                ToolCall(
                    id=item.get("id", item["function"]["name"]),
                    name=item["function"]["name"],
                    arguments=arguments,
                )
            )
        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            raw=data,
        )


class MockLLM(LLMBackend):
    """Deterministic backend for tests and examples."""

    def __init__(
        self,
        responses: list[LLMResponse] | None = None,
        *,
        prefix: str = "mock",
    ) -> None:
        self.responses = list(responses or [])
        self.prefix = prefix
        self.calls: list[dict[str, Any]] = []

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        self.calls.append({"messages": messages, "tools": tools})
        if self.responses:
            return self.responses.pop(0)
        content = messages[-1].get("content", "")
        return LLMResponse(content=f"{self.prefix}: {content}")
