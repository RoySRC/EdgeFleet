A2A Protocol
============

The A2A integration mounts an official A2A Protocol 1.0 JSON-RPC facade on an
agent's FastAPI application.

Installation
------------

.. code-block:: console

   $ pip install 'edgefleet[a2a]'

Mounting routes
---------------

.. code-block:: python

   from edgefleet.integrations.a2a import mount_a2a

   app = agent.create_app()
   mount_a2a(app, agent)

Default routes:

* Agent Card: ``/.well-known/a2a-agent-card.json``
* JSON-RPC: ``/a2a``

Requests to the JSON-RPC route require:

.. code-block:: text

   A2A-Version: 1.0

Mapping
-------

An A2A text message becomes an EdgeFleet
:class:`~edgefleet.models.TaskRequest`. A2A message metadata can provide:

* ``skill``;
* ``allow_actions``;
* ``approved_actions``.

Completed EdgeFleet output is returned as an A2A data message. Failed output
is returned as a text message.

Security
--------

The mounted facade does not automatically inherit the native route's
``Depends`` bearer dependency. Apply FastAPI middleware, a reverse proxy, or
an A2A-supported security scheme before exposing it outside a trusted network.

Limitations
-----------

The current executor returns immediate messages. It does not expose all
EdgeFleet pause/resume semantics as long-running A2A tasks. Add a task-based
A2A executor if external peers must resume action approvals through A2A.

