Agents and skills
=================

Creating an agent
-----------------

.. code-block:: python

   from edgefleet import EdgeAgent, OpenAICompatibleLLM

   agent = EdgeAgent(
       agent_id="vision-edge-1",
       name="Vision edge device",
       endpoint="http://vision-edge-1.local:8100",
       description="Camera inspection agent",
       llm=OpenAICompatibleLLM(
           model="qwen3:4b",
           base_url="http://127.0.0.1:8080/v1",
       ),
       orchestrator_url="http://orchestrator.local:8000",
       orchestrator_token="application-token",
       token="device-token",
   )

Agent descriptors
-----------------

An agent advertises:

* stable ID and name;
* network endpoint;
* version and description;
* skills and tags;
* metadata and last-seen timestamp.

The native descriptor is served at
``/.well-known/agent-card.json``.

Deterministic skills
--------------------

Use deterministic skills when a direct implementation is safer and simpler:

.. code-block:: python

   @agent.skill(
       "inspect_part",
       description="Inspect a component using the local camera",
       tags=["vision", "inspection"],
       input_schema={
           "type": "object",
           "properties": {"part": {"type": "string"}},
           "required": ["part"],
       },
   )
   async def inspect_part(task):
       return await camera.inspect(task.input["part"])

The handler receives the complete
:class:`~edgefleet.models.TaskRequest`. Its return value becomes task output.

Prompt-backed skills
--------------------

A prompt-backed skill advertises a capability while routing execution through
the LLM reasoning engine:

.. code-block:: python

   agent.prompt_skill(
       "diagnose",
       description="Diagnose equipment faults",
       prompt_template=(
           "Diagnose {input}.\n"
           "Device context: {context}\n"
           "Return likely causes, verification checks, and safe actions."
       ),
   )

Prompt templates may use:

* ``input``;
* ``context``;
* ``metadata``;
* ``skill``;
* ``conversation_id``;
* ``goal_id``.

General chat
------------

An agent with an LLM automatically advertises a ``chat`` skill unless a skill
with that name already exists. If no deterministic handler matches, the task
is processed by the reasoning engine.

Startup registration
--------------------

When ``orchestrator_url`` is configured, the agent registers during FastAPI
startup. The advertised ``endpoint`` must be reachable from the orchestrator;
``127.0.0.1`` is usually wrong for containers or separate devices.

Serving an agent
----------------

.. code-block:: python

   import uvicorn

   uvicorn.run(agent.create_app(), host="0.0.0.0", port=8100)

Or use the CLI factory:

.. code-block:: console

   $ edgefleet agent --factory my_agent:create_agent --port 8100

