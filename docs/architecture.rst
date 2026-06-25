Architecture
============

System layout
-------------

.. code-block:: text

   Application
       |
       | EdgeFleet HTTP API
       v
   Orchestrator
       |
       | capability routing / explicit target
       v
   Edge agent
       +---- deterministic skill
       +---- local LLM reasoning
       |       +---- memory
       |       +---- retrieval
       |       +---- delegation
       |       +---- tool selection
       |
       +---- action registry
               +---- Python action
               +---- MCP tool
               +---- ROS 2 action
                        |
                        v
                  MoveIt / ros2_control / hardware

Task lifecycle
--------------

1. A client submits a :class:`~edgefleet.models.TaskRequest`.
2. The orchestrator stores a routing result.
3. The router selects an agent by ``target_agent`` or ``skill``.
4. The orchestrator calls the local agent object or its HTTP endpoint.
5. A deterministic skill runs directly, or the reasoning engine invokes the
   configured LLM.
6. Tool calls are validated and either executed or converted into approval
   checkpoints.
7. The resulting :class:`~edgefleet.models.TaskResult` is stored and returned.

Separation of concerns
----------------------

Control plane
   Agent registration, routing, task state, goals, and approvals.

Reasoning plane
   Prompt construction, model calls, retrieval, planning, reflection, search,
   and debate.

Action plane
   Validated tool execution and integration adapters.

Real-time plane
   ROS 2 controllers, firmware, PLCs, watchdogs, and hardware safety systems.
   This plane must not depend on LLM latency or availability.

Networking
----------

The native transport is HTTP. A2A provides agent interoperability and NATS can
provide request/reply connectivity where direct inbound HTTP is inconvenient.
For routed or Wi-Fi robotics deployments, configure the ROS 2 middleware
independently, for example with a Zenoh-based deployment.

Persistence
-----------

Two persistence scopes exist:

* orchestrator state stores agents, task results, and goals;
* agent runtime state stores conversation memory and paused checkpoints.

Both have in-memory and JSON-file implementations. JSON storage assumes one
writer process.

