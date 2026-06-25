Overview
========

EdgeFleet separates probabilistic language-model reasoning from deterministic
software and hardware execution.

Core responsibilities
---------------------

Orchestrator
   Registers agents, stores task results, routes requests by target or skill,
   resumes paused tasks, and manages persistent goals.

Edge agent
   Advertises capabilities, runs deterministic Python skills, invokes a local
   LLM, executes approved tools, and stores conversation or checkpoint state.

LLM backend
   Converts user intent into responses or structured tool calls. The supplied
   OpenAI-compatible adapter works with llama.cpp, Ollama, vLLM, and similar
   servers.

Action layer
   Validates tool arguments against JSON Schema and enforces ``safe``,
   ``controlled``, or ``dangerous`` policy.

Integration layer
   Connects EdgeFleet to A2A, MCP, NATS, ROS 2, and LangGraph without making
   those systems mandatory core dependencies.

What can run without an LLM
---------------------------

Deterministic skills do not invoke a model:

.. code-block:: python

   @agent.skill("read_encoder")
   async def read_encoder(task):
       return await encoder.read()

This is the preferred path for fixed commands, health checks, sensor reads,
and operations where natural-language reasoning adds no value.

What uses an LLM
----------------

An LLM-backed task may:

* interpret natural-language input;
* select tools and construct validated arguments;
* create and execute a plan;
* compare candidate answers;
* retrieve local reference documents;
* delegate bounded subtasks;
* ask a human for missing information;
* synthesize tool or agent results into a final response.

The LLM does not directly drive actuators. Physical operations must pass
through registered actions and downstream safety controls.

Project status
--------------

Version 0.0.0 is a development foundation. The included JSON persistence stores
are suitable for a single process. Multi-replica production deployments
require a transactional database, authenticated device identities, telemetry,
retry policy, and a dedicated approval service.
