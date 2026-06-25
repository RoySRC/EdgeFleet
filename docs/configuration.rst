Configuration
=============

Environment variables
---------------------

.. list-table::
   :header-rows: 1

   * - Variable
     - Used by
     - Meaning
   * - ``EDGEFLEET_TOKEN``
     - Orchestrator, client, agent registration
     - Bearer token for the orchestrator API.
   * - ``EDGEFLEET_EDGE_TOKEN``
     - Orchestrator and edge agent
     - Bearer token used for orchestrator-to-agent requests.
   * - ``EDGEFLEET_STATE_FILE``
     - CLI orchestrator
     - JSON path for persistent agents, tasks, and goals.
   * - ``EDGEFLEET_ORCHESTRATOR_URL``
     - Example agent
     - URL used for registration and delegation.
   * - ``EDGEFLEET_AGENT_ID``
     - Example agent
     - Stable device identity.
   * - ``EDGEFLEET_AGENT_NAME``
     - Example agent
     - Human-readable device name.
   * - ``EDGEFLEET_AGENT_ENDPOINT``
     - Example agent
     - URL advertised to the orchestrator.
   * - ``EDGEFLEET_AGENT_STATE``
     - Example agent
     - JSON path for memory and checkpoints.
   * - ``EDGEFLEET_MODEL``
     - Example agent
     - Model identifier sent to the inference server.
   * - ``EDGEFLEET_LLM_URL``
     - Example agent
     - OpenAI-compatible ``/v1`` endpoint.
   * - ``EDGEFLEET_LLM_API_KEY``
     - Example agent
     - API key sent to the inference endpoint.

Model configuration
-------------------

.. code-block:: python

   llm = OpenAICompatibleLLM(
       model="qwen3:4b",
       base_url="http://127.0.0.1:8080/v1",
       api_key="local",
       timeout=120,
       temperature=0.1,
   )

Use a low temperature for tool execution and operational workflows. Sampling
strategies such as self-consistency still make multiple calls, but output
diversity depends on the underlying server and model configuration.

Timeouts
--------

``TaskRequest.timeout_seconds`` is used by the orchestrator for remote HTTP
dispatch. The client timeout also becomes the task timeout when using
``EdgeFleetClient.submit``.

Limits
------

Reasoning limits are validated by Pydantic:

* samples and branches: 2--8;
* tree depth: 1--5;
* debate rounds: 1--5;
* retrieval results: 1--20;
* delegation depth: 0--8.

These limits bound cost and reduce accidental loops. Tune them conservatively
for memory-constrained devices.

