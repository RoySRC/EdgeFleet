Quickstart
==========

This walkthrough starts one orchestrator, one edge agent, and an Ollama model.

1. Start the model
------------------

.. code-block:: console

   $ ollama pull qwen3:1.7b
   $ ollama serve

2. Start the orchestrator
-------------------------

.. code-block:: console

   $ export EDGEFLEET_TOKEN=development-secret
   $ export EDGEFLEET_EDGE_TOKEN=edge-secret
   $ edgefleet orchestrator --port 8000

3. Start the example agent
--------------------------

In another terminal:

.. code-block:: console

   $ export EDGEFLEET_TOKEN=development-secret
   $ export EDGEFLEET_EDGE_TOKEN=edge-secret
   $ export EDGEFLEET_ORCHESTRATOR_URL=http://127.0.0.1:8000
   $ edgefleet agent \
       --factory examples.edge_agent:create_agent \
       --port 8100

The example publishes:

* an ``echo`` deterministic skill;
* a ``diagnose`` prompt-backed skill;
* a safe temperature tool;
* a controlled indicator tool;
* a small local retrieval corpus.

4. Submit a deterministic task
------------------------------

.. code-block:: console

   $ curl http://127.0.0.1:8000/v1/tasks \
       -H 'Authorization: Bearer development-secret' \
       -H 'Content-Type: application/json' \
       -d '{"input":{"message":"hello"},"skill":"echo"}'

5. Submit a reasoning task
--------------------------

.. code-block:: python

   import asyncio

   from edgefleet import (
       EdgeFleetClient,
       ReasoningConfig,
       ReasoningMode,
   )


   async def main() -> None:
       client = EdgeFleetClient(
           "http://127.0.0.1:8000",
           token="development-secret",
       )
       result = await client.submit(
           "Diagnose actuator overheating.",
           skill="diagnose",
           conversation_id="actuator-7",
           context={"device": "actuator-7"},
           reasoning=ReasoningConfig(
               mode=ReasoningMode.PLAN_EXECUTE,
               reflection=True,
               memory=True,
               retrieval=True,
           ),
       )
       print(result.model_dump_json(indent=2))


   asyncio.run(main())

6. Use Docker Compose
---------------------

The included stack starts the orchestrator, edge agent, Ollama, model puller,
and NATS:

.. code-block:: console

   $ docker compose up --build

Open ``http://127.0.0.1:8000/docs`` for the generated OpenAPI interface.

