Approvals, checkpoints, and goals
=================================

Action policies
---------------

Actions use one of three policies:

``safe``
   May execute when the task allows actions.

``controlled``
   Requires its name in ``approved_actions``.

``dangerous``
   Also requires explicit approval. Applications should apply stronger
   external policy and hardware controls.

Registering an action
---------------------

.. code-block:: python

   from edgefleet import ActionPolicy, ActionRegistry

   actions = ActionRegistry()

   @actions.action(
       "set_gripper",
       description="Set gripper opening in millimeters",
       input_schema={
           "type": "object",
           "properties": {"opening_mm": {"type": "number"}},
           "required": ["opening_mm"],
           "additionalProperties": False,
       },
       policy=ActionPolicy.DANGEROUS,
   )
   async def set_gripper(opening_mm: float):
       return {"opening_mm": opening_mm}

Approval pause
--------------

If the LLM requests an unapproved controlled action, execution returns
``waiting_approval`` with one or more
:class:`~edgefleet.models.ApprovalRequest` objects.

.. code-block:: python

   result = await client.submit(
       "Open the gripper to 20 mm",
       allow_actions=True,
   )

   if result.state == "waiting_approval":
       result = await client.resume(
           result.task_id,
           approved_actions={"set_gripper"},
       )

The checkpoint preserves the original model tool call. Resume executes the
approved call rather than asking the model to regenerate it.

Human-input conversations
-------------------------

With ``human_approval=True``, the model receives a
``request_human_input`` tool. Calling it returns ``waiting_input``:

.. code-block:: python

   result = await client.resume(
       result.task_id,
       human_input="Use bin B",
   )

If a checkpoint contains both a human question and an action approval, partial
resume data is persisted until every requirement is satisfied.

Persistent checkpoints
----------------------

Use :class:`~edgefleet.state.JsonFileRuntimeState` to survive an agent restart.
The replacement agent must use the same action names, model-compatible message
format, and state file.

Goals
-----

A goal wraps a task with durable lifecycle state:

.. code-block:: python

   from edgefleet import TaskRequest

   goal = await client.create_goal(
       "Complete the component inspection",
       TaskRequest(
           input="Inspect part A-17",
           skill="inspect_part",
       ),
   )

Goal states map from task states:

* active;
* waiting approval;
* waiting input;
* paused;
* completed;
* failed.

Resume a goal:

.. code-block:: python

   goal = await client.resume_goal(
       goal.id,
       approved_actions={"move_camera"},
   )

Orchestrator persistence
------------------------

.. code-block:: console

   $ edgefleet orchestrator \
       --state-file /var/lib/edgefleet/orchestrator.json

The file stores agents, task results, and goals. Use a database-backed store
for concurrent replicas, transactions, audit retention, and high availability.
