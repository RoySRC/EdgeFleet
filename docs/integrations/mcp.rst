Model Context Protocol
======================

MCP tools can be imported into an agent's
:class:`~edgefleet.actions.ActionRegistry`.

Installation
------------

.. code-block:: console

   $ pip install 'edgefleet[mcp]'

Import tools
------------

.. code-block:: python

   from edgefleet.integrations.mcp import MCPToolProvider

   provider = MCPToolProvider("http://127.0.0.1:9000/mcp")
   imported = await provider.load_into(agent.actions)

The provider:

1. opens an MCP Streamable HTTP session;
2. initializes the session;
3. lists server tools;
4. creates one EdgeFleet action per tool;
5. forwards calls to the MCP server.

Policy
------

Imported tools default to ``controlled``:

.. code-block:: python

   from edgefleet import ActionPolicy

   provider = MCPToolProvider(
       "http://127.0.0.1:9000/mcp",
       policy=ActionPolicy.DANGEROUS,
   )

Select the policy based on the strongest effect any imported tool can have.
For mixed-risk servers, register tools individually or split them across MCP
servers with different trust boundaries.

Results
-------

Structured MCP content is returned directly. Otherwise, MCP content items are
converted to JSON-compatible dictionaries when possible.

Operational considerations
--------------------------

The current adapter opens a new session for tool discovery and for each call.
For high-throughput deployments, implement connection reuse with health checks
and reconnect behavior.

