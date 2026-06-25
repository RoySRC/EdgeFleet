Deployment
==========

Single-host Docker Compose
--------------------------

The included ``compose.yaml`` starts:

* EdgeFleet orchestrator;
* example edge agent;
* Ollama;
* model-pull helper;
* NATS with JetStream enabled.

.. code-block:: console

   $ export EDGEFLEET_TOKEN=replace-me
   $ export EDGEFLEET_EDGE_TOKEN=replace-me-too
   $ docker compose up --build

Persistent volumes hold Ollama models and EdgeFleet JSON state.

Multiple physical devices
-------------------------

Run the orchestrator on a stable host and one agent per device:

.. code-block:: text

   orchestrator.local:8000
      |
      +-- camera-1.local:8100
      +-- robot-1.local:8100
      +-- sensor-1.local:8100

Each agent must advertise an endpoint reachable from the orchestrator:

.. code-block:: console

   $ export EDGEFLEET_AGENT_ENDPOINT=http://camera-1.local:8100
   $ export EDGEFLEET_ORCHESTRATOR_URL=http://orchestrator.local:8000

Inference placement
-------------------

Per-device inference
   Each edge agent talks to a model server on localhost. This maximizes local
   operation and data isolation.

Shared inference host
   Multiple agents use one model server. This reduces model duplication but
   creates a network and availability dependency.

Hybrid
   Small models run locally and selected tasks are delegated to a larger local
   server. Apply explicit data-routing policy.

Persistent state
----------------

Orchestrator:

.. code-block:: console

   $ edgefleet orchestrator \
       --state-file /data/orchestrator.json

Agent:

.. code-block:: python

   agent = EdgeAgent(
       ...,
       state=JsonFileRuntimeState("/data/agent.json"),
   )

Back up both scopes if goals, approvals, and conversation history must survive
device loss.

Health checks
-------------

Both services expose:

.. code-block:: text

   GET /health

The response verifies process availability, not model health, tool health,
ROS connectivity, or actuator readiness. Production deployments should add
dependency-specific probes and telemetry.

Scaling
-------

The included stores are not suitable for multiple orchestrator replicas.
Before horizontal scaling:

* implement a transactional store;
* use leases or heartbeats for agent liveness;
* make task submission idempotent;
* add distributed locking for resume operations;
* isolate tenants and authorization scopes;
* add retries with backoff and circuit breakers.

Observability
-------------

Recommended telemetry:

* task and goal state transitions;
* routing decisions;
* model latency and token usage;
* tool calls and approval identity;
* delegation tree and depth;
* retrieval source IDs;
* ROS action acceptance, completion, and timeout;
* device CPU, memory, temperature, and accelerator utilization.

Do not log secrets, raw credentials, or sensitive prompt content by default.

Rolling upgrades
----------------

Paused checkpoints contain model-formatted messages and pending tool names.
When upgrading:

* preserve tool names and schemas until old checkpoints drain;
* keep model/API compatibility;
* version state formats before making breaking changes;
* test resume behavior across the target versions.

