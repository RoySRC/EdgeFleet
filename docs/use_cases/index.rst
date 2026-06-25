Use-case cookbook
=================

This cookbook contains 236 Python programs, one for every use case in the
EdgeFleet catalog. The examples are intentionally small: they show the EdgeFleet
composition point while leaving device drivers, domain schemas, credentials,
and validated controllers to the application.

Most examples submit to an existing orchestrator. Matching agents must
advertise the shown skill and target ID. Integration examples instead show
agent-side adapter setup.

Run a catalog entry
-------------------

The checked-in catalog also provides a generic runner:

.. code-block:: console

   $ python -m examples.use_cases.run \
       robotics-robot-arm-task-planning

List available slugs:

.. code-block:: console

   $ python -m examples.use_cases.run --list

Safety
------

Programs involving physical actions demonstrate approval and orchestration.
They do not replace deterministic controllers, interlocks, collision
checking, emergency stop, regulated validation, or qualified human review.

Detailed examples
-----------------

.. toctree::
   :maxdepth: 1

   lab_automation_cell
   trading_operations_copilot
   earthquake_map_rescue_cookbook

Catalog
-------

.. toctree::
   :maxdepth: 1

   robotics
   industrial
   iot
   smart_buildings
   agriculture
   logistics
   transportation
   healthcare
   retail
   edge_it
   remote
   privacy
   multi_agent
   reasoning_workflows
   knowledge
   approvals
   gateways
   research
   product_patterns
   boundaries
