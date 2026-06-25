LangGraph routing
=================

The default capability router is deterministic. The LangGraph adapter allows
a compiled graph to choose the target agent.

Installation
------------

.. code-block:: console

   $ pip install 'edgefleet[langgraph]'

Graph contract
--------------

The graph receives:

.. code-block:: python

   {
       "task": task.model_dump(mode="json"),
       "agents": [
           agent.model_dump(mode="json")
           for agent in agents
       ],
   }

It must return:

.. code-block:: python

   {"agent_id": "selected-agent"}

Usage
-----

.. code-block:: python

   from edgefleet import Orchestrator
   from edgefleet.routing import LangGraphRouter

   compiled_graph = graph_builder.compile()

   orchestrator = Orchestrator(
       router=LangGraphRouter(compiled_graph),
   )

Validation
----------

The adapter verifies that the returned ID exists in the provided agent list.
An unknown selection fails routing.

Recommended policy
------------------

Keep hard constraints outside the model:

* filter offline or unauthorized agents before graph selection;
* enforce skill compatibility;
* cap task and delegation depth;
* use deterministic routing for safety-critical operations;
* record graph decisions for audit.

