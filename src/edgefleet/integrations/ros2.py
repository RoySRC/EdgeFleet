from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from edgefleet.actions import Action, ActionPolicy


class ROS2ActionAdapter:
    """Wrap a typed ROS 2 action as an EdgeFleet action.

    ROS message packages remain application-specific. The caller supplies the
    action type and functions for converting JSON arguments to a ROS goal and
    the ROS result back to JSON-compatible output.
    """

    def __init__(
        self,
        *,
        node_name: str,
        action_name: str,
        action_type: Any,
        goal_factory: Callable[[dict[str, Any]], Any],
        result_mapper: Callable[[Any], Any] | None = None,
        wait_timeout: float = 10,
    ) -> None:
        self.node_name = node_name
        self.action_name = action_name
        self.action_type = action_type
        self.goal_factory = goal_factory
        self.result_mapper = result_mapper or (lambda value: str(value))
        self.wait_timeout = wait_timeout

    def as_action(
        self,
        *,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        policy: ActionPolicy = ActionPolicy.DANGEROUS,
    ) -> Action:
        async def execute(**arguments: Any) -> Any:
            return await asyncio.to_thread(self._execute_sync, arguments)

        return Action(
            name=name,
            description=description,
            input_schema=input_schema,
            policy=policy,
            handler=execute,
        )

    def _execute_sync(self, arguments: dict[str, Any]) -> Any:
        try:
            import rclpy
            from rclpy.action import ActionClient
        except ImportError as exc:
            raise RuntimeError(
                "rclpy is supplied by a ROS 2 installation. Source the ROS "
                "environment before starting this agent."
            ) from exc

        started_context = not rclpy.ok()
        if started_context:
            rclpy.init()
        node = rclpy.create_node(self.node_name)
        try:
            client = ActionClient(
                node, self.action_type, self.action_name
            )
            if not client.wait_for_server(timeout_sec=self.wait_timeout):
                raise TimeoutError(
                    f"ROS 2 action server unavailable: {self.action_name}"
                )
            goal = self.goal_factory(arguments)
            goal_future = client.send_goal_async(goal)
            rclpy.spin_until_future_complete(node, goal_future)
            goal_handle = goal_future.result()
            if not goal_handle.accepted:
                raise RuntimeError("ROS 2 action goal was rejected")
            result_future = goal_handle.get_result_async()
            rclpy.spin_until_future_complete(node, result_future)
            return self.result_mapper(result_future.result().result)
        finally:
            node.destroy_node()
            if started_context:
                rclpy.shutdown()

