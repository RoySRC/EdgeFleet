ROS 2 and robot actions
=======================

The ROS 2 adapter wraps a typed action server as an EdgeFleet action.

Design boundary
---------------

.. code-block:: text

   LLM intent
      |
      v
   validated EdgeFleet action
      |
      v
   ROS 2 action server
      |
      v
   MoveIt / ros2_control
      |
      v
   hardware controller and safety systems

The LLM must not publish raw motor torque, velocity, or joint commands without
a deterministic safety layer.

Example
-------

.. code-block:: python

   from control_msgs.action import GripperCommand

   from edgefleet.integrations.ros2 import ROS2ActionAdapter


   def make_goal(arguments):
       goal = GripperCommand.Goal()
       goal.command.position = arguments["position"]
       goal.command.max_effort = arguments["max_effort"]
       return goal


   def map_result(result):
       return {
           "position": result.position,
           "effort": result.effort,
           "stalled": result.stalled,
           "reached_goal": result.reached_goal,
       }


   action = ROS2ActionAdapter(
       node_name="edgefleet_gripper",
       action_name="/gripper_controller/gripper_cmd",
       action_type=GripperCommand,
       goal_factory=make_goal,
       result_mapper=map_result,
       wait_timeout=10,
   ).as_action(
       name="move_gripper",
       description="Move the robot gripper",
       input_schema={
           "type": "object",
           "properties": {
               "position": {"type": "number"},
               "max_effort": {"type": "number"},
           },
           "required": ["position", "max_effort"],
           "additionalProperties": False,
       },
   )

   agent.actions.register(action)

Execution behavior
------------------

The adapter:

1. initializes ``rclpy`` if necessary;
2. creates a node and action client;
3. waits for the server;
4. maps JSON arguments to a typed goal;
5. sends and waits for the goal result;
6. maps the typed result to JSON-compatible output;
7. destroys the temporary node.

The blocking ROS spin is run in a worker thread so it does not block the
agent's async event loop.

Safety requirements
-------------------

For physical systems, independently enforce:

* collision-aware planning;
* workspace, speed, acceleration, force, and torque limits;
* controller watchdogs;
* command freshness and replay protection;
* hardware interlocks and emergency stop;
* human exclusion zones where required;
* simulation and hardware-in-the-loop testing.

Networking
----------

ROS 2 middleware configuration is outside EdgeFleet. For Wi-Fi, NAT, or
routed deployments, configure appropriate discovery and routing, potentially
using a Zenoh RMW or router architecture.

