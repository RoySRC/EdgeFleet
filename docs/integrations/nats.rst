NATS
====

The NATS adapter provides request/reply task transport for networks where
direct inbound HTTP access is inconvenient.

Installation
------------

.. code-block:: console

   $ pip install 'edgefleet[nats]'

Start a server with JetStream enabled:

.. code-block:: console

   $ nats-server -js

Serving an agent
----------------

.. code-block:: python

   from edgefleet.integrations.nats import NATSTaskTransport

   transport = NATSTaskTransport(
       ["nats://nats.local:4222"],
       subject_prefix="edgefleet.tasks",
   )
   await transport.connect()
   await transport.serve(agent.agent_id, agent.execute)

Submitting
----------

.. code-block:: python

   result = await transport.request("vision-edge", task)

Subjects use:

.. code-block:: text

   <subject_prefix>.<agent_id>

Lifecycle
---------

Call ``close`` during shutdown to drain the client and subscriptions.

Limitations
-----------

The adapter uses ordinary request/reply. It does not currently publish tasks
to durable JetStream consumers, so offline delivery, replay, and work-queue
semantics are not provided. Implement a JetStream dispatcher before depending
on tasks surviving disconnection.

Security
--------

Configure NATS accounts, credentials, TLS, subject permissions, and leaf-node
policy at the NATS layer. Do not expose an unauthenticated server to an
untrusted network.

