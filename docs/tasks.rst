Tasks and results
=================

Task request
------------

:class:`~edgefleet.models.TaskRequest` is the unit of work submitted through
the Python client or HTTP API.

Important fields
~~~~~~~~~~~~~~~~

``input``
   Arbitrary JSON-compatible input or a plain string.

``skill``
   Optional capability name. The router only considers agents that advertise
   this skill.

``target_agent``
   Optional explicit agent ID. When both target and skill are supplied, both
   constraints must match.

``context``
   Runtime facts injected into prompt construction and forwarded to delegated
   tasks. Use it for device, site, session, or workflow context.

``metadata``
   Application metadata. It is included in dynamic prompt context and can be
   used for tracing or policy.

``conversation_id``
   Selects conversation memory when ``reasoning.memory`` is enabled.

``goal_id``
   Associates the task with a persistent goal.

``reasoning``
   A :class:`~edgefleet.models.ReasoningConfig`.

``allow_actions``
   Must be true before any registered action can execute.

``approved_actions``
   Names of controlled or dangerous actions already approved by the caller.

``timeout_seconds``
   Maximum remote-dispatch timeout, between one second and one hour.

Task states
-----------

.. list-table::
   :header-rows: 1

   * - State
     - Meaning
   * - ``submitted``
     - Accepted but not yet routed.
   * - ``routing``
     - Orchestrator is selecting an agent.
   * - ``running``
     - Agent execution is active.
   * - ``waiting_approval``
     - One or more controlled actions require approval.
   * - ``waiting_input``
     - The agent requested additional human input.
   * - ``paused``
     - Execution is intentionally suspended.
   * - ``completed``
     - Final output is available.
   * - ``failed``
     - Execution raised an error.
   * - ``rejected``
     - Policy rejected the request.

Task result
-----------

:class:`~edgefleet.models.TaskResult` contains:

* the final or current state;
* output or error;
* assigned agent ID;
* timestamps;
* a structured trace;
* pending approval requests;
* a pending human question.

Traces
------

The trace records operational artifacts such as:

* plans;
* retrieval document IDs;
* tool arguments and results;
* self-consistency candidates;
* tree or graph search structures;
* debate transcripts;
* reflection critiques;
* concise decision summaries.

Do not treat traces as hidden chain-of-thought. EdgeFleet deliberately records
bounded, application-visible reasoning artifacts rather than private
token-by-token model reasoning.

HTTP API
--------

Submit:

.. code-block:: text

   POST /v1/tasks
   Authorization: Bearer <token>
   Content-Type: application/json

   {
     "input": "Inspect part A-17",
     "skill": "inspect_part",
     "reasoning": {"mode": "direct"}
   }

Get state:

.. code-block:: text

   GET /v1/tasks/{task_id}
   Authorization: Bearer <token>

Resume:

.. code-block:: text

   POST /v1/tasks/{task_id}/resume
   Authorization: Bearer <token>
   Content-Type: application/json

   {"approved_actions": ["move_camera"]}
