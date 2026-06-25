from __future__ import annotations

from typing import Any

from edgefleet.actions import Action, ActionPolicy, ActionRegistry


class MCPToolProvider:
    """Import tools from an MCP Streamable HTTP server as EdgeFleet actions."""

    def __init__(
        self,
        url: str,
        *,
        policy: ActionPolicy = ActionPolicy.CONTROLLED,
    ) -> None:
        self.url = url
        self.policy = policy

    async def load_into(self, registry: ActionRegistry) -> list[Action]:
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as exc:
            raise RuntimeError(
                "Install EdgeFleet with the MCP extra: pip install "
                "'edgefleet[mcp]'"
            ) from exc

        imported: list[Action] = []
        async with streamablehttp_client(self.url) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                response = await session.list_tools()
                for tool in response.tools:
                    name = tool.name

                    async def invoke(
                        _tool_name: str = name,
                        **arguments: Any,
                    ) -> Any:
                        return await self.call(_tool_name, arguments)

                    action = Action(
                        name=name,
                        description=tool.description or f"MCP tool {name}",
                        input_schema=tool.inputSchema,
                        policy=self.policy,
                        handler=invoke,
                    )
                    registry.register(action)
                    imported.append(action)
        return imported

    async def call(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> Any:
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as exc:
            raise RuntimeError(
                "Install EdgeFleet with the MCP extra: pip install "
                "'edgefleet[mcp]'"
            ) from exc

        async with streamablehttp_client(self.url) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                if getattr(result, "structuredContent", None) is not None:
                    return result.structuredContent
                return [
                    item.model_dump(mode="json")
                    if hasattr(item, "model_dump")
                    else str(item)
                    for item in result.content
                ]

