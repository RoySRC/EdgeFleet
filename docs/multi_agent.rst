Multi-agent communication
=========================

Orchestrator-mediated communication
-----------------------------------

The default topology is:

.. code-block:: text

   Agent A -> Orchestrator -> Agent B

This centralizes authentication, routing, task state, depth limits, and cycle
detection.

Explicit delegation
-------------------

An application or deterministic skill can submit to another agent:

.. code-block:: python

   result = await fleet.submit(
       "Inspect the bearing image",
       skill="inspect_image",
       target_agent="vision-edge",
   )

Automatic delegation
--------------------

When enabled, the LLM receives ``delegate_task``:

.. code-block:: python

   ReasoningConfig(
       auto_delegate=True,
       max_delegation_depth=2,
   )

The tool accepts:

* target agent ID;
* optional skill;
* bounded request text.

Child tasks include the parent task ID, current depth, visited agents, and
delegating agent. Automatic delegation is disabled in child reasoning
configuration to prevent uncontrolled recursive chains.

Cycle protection
----------------

Delegation rejects:

* self-delegation;
* agents already in the visited set;
* requests at or above the configured depth.

These controls prevent simple loops, but applications should also set total
workflow budgets and deadlines.

Multi-agent debate
------------------

Named debate participants receive each round through delegation:

.. code-block:: python

   ReasoningConfig(
       mode=ReasoningMode.DEBATE,
       debate_agents=[
           "perception-agent",
           "safety-agent",
           "maintenance-agent",
       ],
       debate_rounds=2,
   )

The moderator records positions and asks its own LLM to resolve the final
round. Participants should have distinct information or responsibilities;
running identical models with identical context often adds cost without
meaningful diversity.

Direct A2A communication
------------------------

The optional A2A facade allows protocol-compatible peers to contact an agent
directly. EdgeFleet's native automatic delegation currently uses the
orchestrator API, not the outgoing A2A client transport.

Failure handling
----------------

A delegated task must complete successfully. Waiting, rejected, or failed
child tasks become an error in the parent tool loop. For workflows requiring
nested approvals, implement an orchestrator-level workflow policy that exposes
child state to the caller.

