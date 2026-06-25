Testing and development
=======================

Run tests
---------

.. code-block:: console

   $ pip install -e '.[test]'
   $ pytest

The suite covers:

* deterministic skills;
* tool execution and approval resume;
* native API authentication;
* local orchestrator routing;
* A2A discovery and messaging;
* all reasoning modes;
* reflection and decision summaries;
* memory, retrieval, and prompt templates;
* human-input checkpoints;
* delegation and multi-agent debate;
* checkpoint persistence across restart;
* persistent goals and approval resume.

Mock LLM
--------

:class:`~edgefleet.llm.MockLLM` returns deterministic queued responses and
records calls:

.. code-block:: python

   llm = MockLLM(
       [
           LLMResponse(content="first"),
           LLMResponse(content="second"),
       ]
   )

   result = await agent.execute(task)
   assert llm.calls[0]["messages"][1]["content"] == "expected input"

Use it for tool-call fixtures, reasoning-strategy call counts, and prompt
inspection without starting a model server.

API tests
---------

FastAPI applications can be tested in process:

.. code-block:: python

   transport = httpx.ASGITransport(app=orchestrator.create_app())

   async with httpx.AsyncClient(
       transport=transport,
       base_url="http://test",
   ) as client:
       response = await client.get("/health")

Package verification
--------------------

.. code-block:: console

   $ python -m compileall -q src examples tests
   $ pip check
   $ pip wheel . --no-deps -w /tmp/edgefleet-wheel
   $ docker compose config --quiet

Documentation verification
---------------------------

The default Makefile treats Sphinx warnings as errors:

.. code-block:: console

   $ pip install -e '.[docs]'
   $ make -C docs html

For external-link validation:

.. code-block:: console

   $ make -C docs linkcheck

Hardware testing
----------------

For robot actions, add:

* simulation tests;
* controller integration tests;
* hardware-in-the-loop tests;
* fault injection for network and model loss;
* limit and emergency-stop verification;
* tests proving that rejected or stale approvals cannot execute.

