from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from jsonschema import ValidationError, validate

from edgefleet.models import ApprovalRequest


class ActionPolicy(StrEnum):
    SAFE = "safe"
    CONTROLLED = "controlled"
    DANGEROUS = "dangerous"


class ActionRejected(RuntimeError):
    pass


ActionHandler = Callable[..., Any] | Callable[..., Awaitable[Any]]


@dataclass(slots=True)
class Action:
    name: str
    description: str
    handler: ActionHandler
    input_schema: dict[str, Any] = field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )
    policy: ActionPolicy = ActionPolicy.CONTROLLED

    def as_llm_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


class ActionRegistry:
    def __init__(self) -> None:
        self._actions: dict[str, Action] = {}

    def register(self, action: Action) -> Action:
        if action.name in self._actions:
            raise ValueError(f"Action already registered: {action.name}")
        self._actions[action.name] = action
        return action

    def action(
        self,
        name: str,
        *,
        description: str,
        input_schema: dict[str, Any] | None = None,
        policy: ActionPolicy = ActionPolicy.CONTROLLED,
    ) -> Callable[[ActionHandler], ActionHandler]:
        def decorator(handler: ActionHandler) -> ActionHandler:
            self.register(
                Action(
                    name=name,
                    description=description,
                    input_schema=input_schema
                    or {"type": "object", "properties": {}},
                    handler=handler,
                    policy=policy,
                )
            )
            return handler

        return decorator

    def get(self, name: str) -> Action | None:
        return self._actions.get(name)

    def list(self) -> list[Action]:
        return list(self._actions.values())

    def llm_tools(self) -> list[dict[str, Any]]:
        return [action.as_llm_tool() for action in self._actions.values()]

    def approval_requirement(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        task_id: str,
        allow_actions: bool,
        approved_actions: set[str],
    ) -> ApprovalRequest | None:
        action = self.get(name)
        if action is None:
            raise ActionRejected(f"Unknown action: {name}")
        self._validate(action, arguments)
        if not allow_actions:
            raise ActionRejected("Task did not permit action execution")
        if (
            action.policy is not ActionPolicy.SAFE
            and action.name not in approved_actions
        ):
            return ApprovalRequest(
                task_id=task_id,
                action=action.name,
                arguments=arguments,
                policy=action.policy.value,
                prompt=(
                    f"Approve action '{action.name}' with arguments "
                    f"{arguments}?"
                ),
            )
        return None

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        allow_actions: bool,
        approved_actions: set[str],
    ) -> Any:
        action = self.get(name)
        if action is None:
            raise ActionRejected(f"Unknown action: {name}")
        if not allow_actions:
            raise ActionRejected("Task did not permit action execution")
        if (
            action.policy is not ActionPolicy.SAFE
            and action.name not in approved_actions
        ):
            raise ActionRejected(
                f"Action '{name}' requires explicit approval "
                f"(policy={action.policy.value})"
            )
        self._validate(action, arguments)

        result = action.handler(**arguments)
        if inspect.isawaitable(result):
            return await result
        return result

    @staticmethod
    def _validate(action: Action, arguments: dict[str, Any]) -> None:
        try:
            validate(instance=arguments, schema=action.input_schema)
        except ValidationError as exc:
            location = ".".join(str(item) for item in exc.absolute_path)
            suffix = f" at '{location}'" if location else ""
            raise ActionRejected(
                f"Invalid arguments for action '{action.name}'{suffix}: "
                f"{exc.message}"
            ) from exc
