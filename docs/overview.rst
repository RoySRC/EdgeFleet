Overview
========

EdgeFleet separates probabilistic language-model reasoning from deterministic
software and hardware execution.

Purpose
-------

EdgeFleet is a coordination layer for fleets of edge devices that need local
LLM assistance without giving the LLM direct authority over hardware,
production systems, or sensitive data. The project is built for situations
where a human or application wants to issue a high-level request such as:

.. code-block:: text

   Inspect sector A, identify survivors, deliver approved first-aid kits,
   and propose excavation steps for trapped victims.

or:

.. code-block:: text

   Review this machine fault, retrieve the local maintenance manual, ask the
   vibration sensor agent for current readings, and prepare a safe repair plan.

Those requests are too broad for a single deterministic function, but too
risky to hand directly to an unconstrained model. EdgeFleet provides the
middle layer: it lets local models interpret and coordinate work while every
device capability remains explicit, routable, validated, and approval-aware.

The project is intentionally not a robot controller, model server, cloud agent
platform, or real-time automation runtime. It is the glue that lets those
systems work together through a common task API.

Problem statement
-----------------

Existing APIs already cover important pieces of this space. OpenAI-compatible
servers expose local model inference. MCP exposes tools and data to AI
applications. A2A defines agent-to-agent interoperability. ROS 2 actions
provide long-running robot goals with feedback and results. LangGraph provides
durable agent workflow primitives.

The problem EdgeFleet solves is the missing combined layer for edge fleets:
one clean Python package for local edge-agent registration, skill routing,
local LLM use, guarded actions, approvals, resumable goals, and optional
robotics, messaging, tool, and workflow integrations.

Many edge deployments need that combination rather than any single protocol in
isolation:

* devices are distributed across a site, vehicle, robot fleet, lab, factory, or
  remote field operation;
* each device has a different capability, sensor, actuator, local database, or
  model;
* a coordinator needs to route work by target device or advertised skill;
* local LLMs are useful for planning, summarization, triage, delegation, and
  interface translation;
* deterministic Python skills still need to own fixed operations such as
  sensor reads, validation, database lookups, and controller calls;
* actions need structured schemas and explicit safety policy;
* risky physical or business actions need human approval before execution;
* long-running missions need checkpoints, memory, task results, and resumable
  goals;
* ROS 2, NATS, MCP, A2A, and LangGraph should be connectable without becoming
  mandatory core dependencies.

Without that combined layer, teams often have to stitch together model APIs,
robot APIs, messaging systems, tool protocols, prompt code, approval logic, and
state persistence themselves. EdgeFleet provides the package boundary for that
work: it gives applications one task API while keeping existing runtimes
replaceable and keeping real actions explicit, validated, routed, resumable,
and approval-gated.

How EdgeFleet solves it
-----------------------

EdgeFleet solves the problem by making the boundary between reasoning,
routing, and execution explicit.

#. Applications submit work to one task API.
#. The orchestrator stores the task and routes it by target agent or advertised
   skill.
#. Edge agents expose concrete capabilities as deterministic Python skills,
   LLM-backed prompt skills, or guarded actions.
#. Local LLM backends can interpret natural language, create plans, call tools,
   ask for missing information, delegate subtasks, and summarize results.
#. Deterministic skills handle fixed operations such as sensor reads, database
   lookups, state checks, validation, and controller calls.
#. The action layer validates structured arguments against JSON Schema before
   execution.
#. Actions are classified as ``safe``, ``controlled``, or ``dangerous`` so
   EdgeFleet can pause controlled or dangerous work until approval is provided.
#. Runtime state stores checkpoints, conversation memory, and resumable task
   state.
#. Persistent goals let a long-running objective survive pauses, approvals,
   retries, and intermittent network conditions.
#. Integration adapters connect existing infrastructure while keeping the core
   package small.

The result is not an autonomous system that magically controls an environment.
It is a structured way to build systems where local agents can reason,
coordinate, and propose actions while deterministic code and human approval
remain in charge of execution.

Typical fit
-----------

EdgeFleet is a good fit when the application needs:

* one coordinator supervising many local agents;
* local model inference through llama.cpp, Ollama, vLLM, or another
  OpenAI-compatible server;
* clear separation between LLM reasoning and physical or business actions;
* resumable goals and approval checkpoints;
* agent-to-agent delegation;
* device skills that are normal Python functions;
* optional bridges to robotics, messaging, tool, or workflow middleware.

It is a poor fit as the only component for:

* hard real-time control loops;
* emergency-stop logic;
* safety PLC behavior;
* raw flight stabilization;
* autonomous medical decisions;
* unaudited public-internet automation;
* exactly-once distributed delivery without a durable transport extension.

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
