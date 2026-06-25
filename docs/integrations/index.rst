Integrations
============

EdgeFleet keeps optional systems behind adapters. Install only the extras and
external runtimes required by a deployment.

.. toctree::
   :maxdepth: 1

   a2a
   mcp
   nats
   ros2
   langgraph

.. list-table::
   :header-rows: 1

   * - Integration
     - Role
     - Required extra/runtime
   * - A2A
     - Standards-based agent discovery and messaging facade
     - ``edgefleet[a2a]``
   * - MCP
     - Import external tools into an agent action registry
     - ``edgefleet[mcp]``
   * - NATS
     - Request/reply transport for edge connectivity
     - ``edgefleet[nats]`` and a NATS server
   * - ROS 2
     - Wrap typed robot actions
     - ROS 2 and ``rclpy``
   * - LangGraph
     - Custom graph-based agent selection
     - ``edgefleet[langgraph]``

