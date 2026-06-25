Installation
============

Requirements
------------

* Python 3.11 or newer
* A local inference server for LLM-backed tasks
* Optional external runtimes for integrations

Development installation
------------------------

.. code-block:: console

   $ python3 -m venv .venv
   $ source .venv/bin/activate
   $ pip install -e '.[test,docs]'

Core installation
-----------------

.. code-block:: console

   $ pip install .

Optional extras
---------------

.. list-table::
   :header-rows: 1

   * - Extra
     - Purpose
   * - ``a2a``
     - Official A2A Protocol 1.0 HTTP/JSON-RPC facade.
   * - ``mcp``
     - Import tools from MCP Streamable HTTP servers.
   * - ``nats``
     - NATS request/reply task transport.
   * - ``langgraph``
     - Route tasks with a compiled LangGraph graph.
   * - ``docs``
     - Build this Sphinx documentation.
   * - ``test``
     - Run the test suite.
   * - ``all``
     - Install every packaged optional dependency.

ROS 2
-----

``rclpy`` is distributed with ROS 2 rather than through this project's Python
extras. Install ROS 2, install the message packages used by your robot, and
source the ROS environment before starting the agent:

.. code-block:: console

   $ source /opt/ros/jazzy/setup.bash
   $ edgefleet agent --factory my_robot.agent:create_agent

Local inference
---------------

Ollama example:

.. code-block:: console

   $ ollama pull qwen3:1.7b
   $ ollama serve

llama.cpp example:

.. code-block:: console

   $ llama-server -m model.gguf --host 0.0.0.0 --port 8080

Set ``EDGEFLEET_LLM_URL`` to the server's OpenAI-compatible ``/v1`` URL.

Building the documentation
--------------------------

.. code-block:: console

   $ pip install -e '.[docs]'
   $ make -C docs html

The generated site is written to ``docs/_build/html``.

