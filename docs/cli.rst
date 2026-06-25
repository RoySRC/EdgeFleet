Command-line interface
======================

Orchestrator
------------

.. code-block:: console

   $ edgefleet orchestrator \
       --host 0.0.0.0 \
       --port 8000 \
       --token application-token \
       --edge-token device-token \
       --state-file /var/lib/edgefleet/orchestrator.json

Arguments
~~~~~~~~~

``--host``
   Bind address. Defaults to ``0.0.0.0``.

``--port``
   HTTP port. Defaults to ``8000``.

``--token``
   Orchestrator bearer token. Defaults to ``EDGEFLEET_TOKEN``.

``--edge-token``
   Bearer token used when calling remote edge agents. Defaults to
   ``EDGEFLEET_EDGE_TOKEN``.

``--state-file``
   Optional JSON persistence path. Defaults to ``EDGEFLEET_STATE_FILE``.

Edge agent
----------

.. code-block:: console

   $ edgefleet agent \
       --factory my_package.agent:create_agent \
       --host 0.0.0.0 \
       --port 8100

The factory is a ``module:function`` path. It must return an
:class:`~edgefleet.agent.EdgeAgent`.

Python module discovery
~~~~~~~~~~~~~~~~~~~~~~~

The current working directory is added to Python's import path before loading
the factory. Run the command from the project root or install the package that
contains the factory.

