Lab automation cell
===================

Use case
--------

A practical EdgeFleet deployment is a small lab automation cell that sorts
incoming sample tubes into racks. The cell has a tray camera, a barcode/OCR
pipeline, an inventory or LIMS lookup service, a robot arm with a gripper, and
an operator station. The operator gives one high-level instruction:

.. code-block:: text

   Sort tray A. Put unreadable labels aside. Ask before moving the arm.

The system should inspect each tube, identify its label, choose the correct
rack slot, and request approval before any physical arm movement. The useful
work is not just moving the robot. The useful work is coordinating multiple
local devices, preserving state when approval is required, turning ambiguous
operator intent into bounded tasks, and keeping the LLM away from direct
low-level control.

This is a good EdgeFleet use case because the responsibilities are naturally
split across edge devices:

* A lab gateway runs the orchestrator. It owns task routing, durable task
  results, and persistent goals such as "finish sorting tray A".
* A vision edge agent runs deterministic Python skills for camera capture,
  barcode decoding, OCR, and basic defect checks.
* An inventory edge agent validates sample IDs and selects rack positions from
  local inventory data.
* A robot-arm edge agent exposes controlled actions such as ``move_sample`` and
  ``open_gripper``. These actions are validated with JSON Schema and pause for
  human approval.
* A safety or review agent can critique the proposed plan before physical
  execution. It may run on another device or another local model.
* Optional integration adapters connect the same EdgeFleet application to ROS 2,
  MCP, NATS, A2A, and LangGraph without requiring those systems in the core
  package.

The LLM is used for task interpretation, planning, tool-call selection,
ambiguity handling, and natural-language summaries. It is not used for
hard-real-time motor control, collision avoidance, force limiting,
emergency-stop logic, or regulatory validation. Those remain deterministic
controller and safety-system responsibilities.

Normal workflow
---------------

The common execution path is:

#. The operator creates a persistent goal: sort tray A.
#. The orchestrator stores the goal and routes the task to the agent that
   advertises ``sort_tray``.
#. The robot-arm agent uses its local LLM to plan the workflow. With automatic
   delegation enabled, it can ask the vision agent to inspect the tray and the
   inventory agent to choose rack slots.
#. Deterministic skills return structured facts: sample IDs, confidence scores,
   unreadable labels, damage flags, and available rack positions.
#. The robot-arm agent proposes a bounded physical action such as
   ``move_sample({"sample_id": "S-1042", "rack": "B", "slot": "4"})``.
#. The action layer validates the arguments against JSON Schema. Because the
   action is controlled, EdgeFleet pauses the task and returns a pending
   approval request.
#. A human reviews the exact action name and arguments, then approves or
   rejects the action.
#. The orchestrator resumes the paused task. The agent executes the approved
   action through the deterministic robot controller, stores a checkpoint, and
   continues until the goal completes or another approval is needed.

This pattern also handles failures well. If Wi-Fi drops, the orchestrator still
has the current goal and latest task state. If the human pauses the job, the
robot-arm agent has a checkpoint. If the vision result is low-confidence, the
agent can request human input instead of guessing.

Mapping to EdgeFleet responsibilities
-------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Responsibility
     - Use in this example
   * - Orchestrator
     - Registers the vision, inventory, safety, and robot-arm agents. Stores
       task results. Routes by ``target_agent`` or ``skill``. Resumes paused
       approvals. Manages the persistent ``sort tray A`` goal.
   * - Edge agent
     - Advertises capabilities such as ``inspect_tray``, ``assign_rack_slots``,
       ``review_sort_plan``, and ``sort_tray``. Runs deterministic Python
       skills. Invokes a local LLM where planning is useful. Stores memory and
       checkpoints.
   * - LLM backend
     - Uses an OpenAI-compatible local endpoint, such as Ollama, llama.cpp, or
       vLLM, to convert the high-level instruction into a plan and structured
       tool calls.
   * - Action layer
     - Validates action arguments and enforces safe, controlled, or dangerous
       policy. Physical robot movement is controlled and requires explicit
       approval.
   * - Integration layer
     - Optionally maps arm commands to ROS 2 actions, imports camera or lab
       instrument tools from MCP, carries task requests over NATS, exposes A2A,
       or delegates routing decisions to LangGraph.

Reference implementation
------------------------

The following snippets show the shape of a real deployment. They intentionally
keep device drivers simple so the EdgeFleet boundaries are visible.

Orchestrator
~~~~~~~~~~~~

Run this on the lab gateway:

.. code-block:: python

   # lab_orchestrator.py
   import os

   from edgefleet import JsonFileStore, Orchestrator


   orchestrator = Orchestrator(
       store=JsonFileStore("state/lab-orchestrator.json"),
       token=os.getenv("EDGEFLEET_TOKEN"),
       edge_token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
   )

   app = orchestrator.create_app()

Start it with:

.. code-block:: console

   $ uvicorn lab_orchestrator:app --host 0.0.0.0 --port 8000

Vision agent
~~~~~~~~~~~~

The vision agent advertises a deterministic skill. It can still have an LLM for
ambiguous label interpretation, but camera capture, OCR, and barcode decoding
should be deterministic code.

.. code-block:: python

   # vision_agent.py
   import os

   from edgefleet import EdgeAgent, JsonFileRuntimeState, OpenAICompatibleLLM


   llm = OpenAICompatibleLLM(
       model=os.getenv("EDGEFLEET_MODEL", "qwen3:1.7b"),
       base_url=os.getenv("EDGEFLEET_LLM_URL", "http://127.0.0.1:11434/v1"),
       api_key=os.getenv("EDGEFLEET_LLM_API_KEY", "local"),
   )

   agent = EdgeAgent(
       agent_id="vision-agent",
       name="Tray vision agent",
       endpoint="http://vision-box.local:8101",
       description="Local camera, barcode, OCR, and label inspection",
       llm=llm,
       state=JsonFileRuntimeState("state/vision-agent.json"),
       token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
       orchestrator_url="http://lab-gateway.local:8000",
       orchestrator_token=os.getenv("EDGEFLEET_TOKEN"),
   )


   @agent.skill(
       "inspect_tray",
       description="Capture a tray image and return sample IDs and label state.",
       tags=["vision", "deterministic"],
   )
   async def inspect_tray(task):
       tray_id = task.input["tray_id"]

       # Replace this block with camera capture, barcode decoding, OCR, and
       # confidence scoring. Keep the hardware-facing code deterministic.
       return {
           "tray_id": tray_id,
           "samples": [
               {
                   "sample_id": "S-1042",
                   "position": "A1",
                   "label_confidence": 0.99,
                   "defects": [],
               },
               {
                   "sample_id": None,
                   "position": "A2",
                   "label_confidence": 0.41,
                   "defects": ["unreadable_label"],
               },
           ],
       }


   app = agent.create_app()

Inventory agent
~~~~~~~~~~~~~~~

The inventory agent is another deterministic service. It turns sample IDs into
allowed rack slots and isolates bad labels.

.. code-block:: python

   # inventory_agent.py
   import os

   from edgefleet import EdgeAgent, JsonFileRuntimeState


   agent = EdgeAgent(
       agent_id="inventory-agent",
       name="Inventory agent",
       endpoint="http://inventory-box.local:8102",
       description="Local sample lookup and rack-slot assignment",
       state=JsonFileRuntimeState("state/inventory-agent.json"),
       token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
       orchestrator_url="http://lab-gateway.local:8000",
       orchestrator_token=os.getenv("EDGEFLEET_TOKEN"),
   )


   @agent.skill(
       "assign_rack_slots",
       description="Choose rack positions for readable samples.",
       tags=["inventory", "deterministic"],
   )
   async def assign_rack_slots(task):
       assignments = []
       quarantine = []

       for sample in task.input["samples"]:
           if not sample["sample_id"]:
               quarantine.append(
                   {
                       "position": sample["position"],
                       "reason": "unreadable_label",
                   }
               )
               continue

           assignments.append(
               {
                   "sample_id": sample["sample_id"],
                   "from_position": sample["position"],
                   "rack": "B",
                   "slot": "4",
               }
           )

       return {
           "assignments": assignments,
           "quarantine": quarantine,
       }


   app = agent.create_app()

Robot-arm agent
~~~~~~~~~~~~~~~

The robot-arm agent owns the high-level ``sort_tray`` skill. It uses the LLM to
plan and request tool calls, but physical actions are still explicit,
schema-validated EdgeFleet actions.

.. code-block:: python

   # robot_arm_agent.py
   import os

   from edgefleet import (
       ActionPolicy,
       ActionRegistry,
       Document,
       EdgeAgent,
       InMemoryRetriever,
       JsonFileRuntimeState,
       OpenAICompatibleLLM,
   )


   actions = ActionRegistry()


   @actions.action(
       "move_sample",
       description="Move one sample tube from a tray position to a rack slot.",
       input_schema={
           "type": "object",
           "properties": {
               "sample_id": {"type": "string"},
               "from_position": {"type": "string"},
               "rack": {"type": "string"},
               "slot": {"type": "string"},
               "speed": {"type": "string", "enum": ["slow", "normal"]},
           },
           "required": [
               "sample_id",
               "from_position",
               "rack",
               "slot",
               "speed",
           ],
           "additionalProperties": False,
       },
       policy=ActionPolicy.CONTROLLED,
   )
   async def move_sample(
       sample_id: str,
       from_position: str,
       rack: str,
       slot: str,
       speed: str,
   ):
       # Replace this with a deterministic robot controller call. In production,
       # this function should talk to ROS 2, a PLC, or a vendor SDK that already
       # enforces limits, collision checks, and emergency-stop behavior.
       return {
           "sample_id": sample_id,
           "from_position": from_position,
           "destination": f"{rack}:{slot}",
           "speed": speed,
           "status": "completed",
       }


   @actions.action(
       "move_to_service_pose",
       description="Move the robot arm to a service pose for human inspection.",
       input_schema={
           "type": "object",
           "properties": {
               "reason": {"type": "string"},
           },
           "required": ["reason"],
           "additionalProperties": False,
       },
       policy=ActionPolicy.DANGEROUS,
   )
   async def move_to_service_pose(reason: str):
       return {"status": "service_pose_requested", "reason": reason}


   llm = OpenAICompatibleLLM(
       model=os.getenv("EDGEFLEET_MODEL", "qwen3:1.7b"),
       base_url=os.getenv("EDGEFLEET_LLM_URL", "http://127.0.0.1:11434/v1"),
       api_key=os.getenv("EDGEFLEET_LLM_API_KEY", "local"),
   )

   retriever = InMemoryRetriever(
       [
           Document(
               id="lab-cell-safety",
               text=(
                   "Move sample tubes slowly. Do not move unreadable labels "
                   "to normal racks. Quarantine unreadable labels for human "
                   "review. Ask for approval before any arm movement."
               ),
           )
       ]
   )

   agent = EdgeAgent(
       agent_id="robot-arm-agent",
       name="Robot arm coordinator",
       endpoint="http://robot-arm.local:8103",
       description="Plans tray sorting and exposes guarded robot-arm actions",
       llm=llm,
       actions=actions,
       retriever=retriever,
       state=JsonFileRuntimeState("state/robot-arm-agent.json"),
       token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
       orchestrator_url="http://lab-gateway.local:8000",
       orchestrator_token=os.getenv("EDGEFLEET_TOKEN"),
   )

   agent.prompt_skill(
       "sort_tray",
       description="Inspect a tray, assign rack slots, and move samples safely.",
       prompt_template=(
           "You coordinate a lab robot cell.\n"
           "Task: {input}\n"
           "Context: {context}\n"
           "Relevant safety notes: {retrieved_context}\n\n"
           "Required behavior:\n"
           "1. Delegate tray inspection to vision-agent with skill "
           "inspect_tray.\n"
           "2. Delegate rack-slot assignment to inventory-agent with skill "
           "assign_rack_slots.\n"
           "3. Never move unreadable labels to a normal rack.\n"
           "4. For each readable sample, call move_sample with speed='slow'.\n"
           "5. Summarize completed moves and quarantined positions."
       ),
   )


   app = agent.create_app()

Safety review agent
~~~~~~~~~~~~~~~~~~~

The safety agent can be used as an independent reviewer through
``ReasoningConfig.debate_agents`` or as a direct target for a review task.

.. code-block:: python

   # safety_agent.py
   import os

   from edgefleet import EdgeAgent, JsonFileRuntimeState, OpenAICompatibleLLM


   agent = EdgeAgent(
       agent_id="safety-agent",
       name="Lab safety reviewer",
       endpoint="http://safety-box.local:8104",
       description="Reviews proposed lab automation plans before execution",
       llm=OpenAICompatibleLLM(
           model=os.getenv("EDGEFLEET_MODEL", "qwen3:1.7b"),
           base_url=os.getenv("EDGEFLEET_LLM_URL", "http://127.0.0.1:11434/v1"),
           api_key=os.getenv("EDGEFLEET_LLM_API_KEY", "local"),
       ),
       state=JsonFileRuntimeState("state/safety-agent.json"),
       token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
       orchestrator_url="http://lab-gateway.local:8000",
       orchestrator_token=os.getenv("EDGEFLEET_TOKEN"),
   )

   agent.prompt_skill(
       "review_sort_plan",
       description="Critique a proposed sample-sorting plan.",
       prompt_template=(
           "Review this lab automation plan for obvious safety issues. "
           "Check that unreadable labels are quarantined and that arm movement "
           "requires approval.\n\nPlan:\n{input}"
       ),
   )


   app = agent.create_app()

Client program
~~~~~~~~~~~~~~

The operator client creates a persistent goal and resumes it when a pending
approval has been reviewed. Notice that approval is explicit: the client should
show ``pending_approvals`` to the operator before passing action names back to
``resume_goal``.

.. code-block:: python

   # run_sort_tray.py
   import asyncio
   import os

   from edgefleet import (
       EdgeFleetClient,
       GoalState,
       ReasoningConfig,
       ReasoningMode,
       TaskRequest,
   )


   async def main():
       client = EdgeFleetClient(
           os.getenv("EDGEFLEET_URL", "http://lab-gateway.local:8000"),
           token=os.getenv("EDGEFLEET_TOKEN"),
           timeout=300,
       )

       task = TaskRequest(
           input={
               "tray_id": "tray-A",
               "instruction": (
                   "Sort tray A. Put unreadable labels aside. Ask before "
                   "moving the arm."
               ),
           },
           skill="sort_tray",
           target_agent="robot-arm-agent",
           allow_actions=True,
           conversation_id="lab-cell/tray-A",
           reasoning=ReasoningConfig(
               mode=ReasoningMode.PLAN_EXECUTE,
               reflection=True,
               reasoning_summary=True,
               memory=True,
               retrieval=True,
               auto_delegate=True,
               human_approval=True,
               debate_agents=["safety-agent"],
           ),
       )

       goal = await client.create_goal(
           "Sort tray A and quarantine unreadable labels",
           task,
       )
       print(goal.model_dump_json(indent=2))

       while goal.state in {
           GoalState.WAITING_APPROVAL,
           GoalState.WAITING_INPUT,
           GoalState.PAUSED,
       }:
           result = goal.result
           if result and result.pending_approvals:
               for approval in result.pending_approvals:
                   print(approval.model_dump_json(indent=2))

               answer = input("Approve these physical actions? [yes/no] ")
               if answer.lower() != "yes":
                   raise SystemExit("Operator rejected the pending action.")

               goal = await client.resume_goal(
                   goal.id,
                   approved_actions={
                       approval.action
                       for approval in result.pending_approvals
                   },
               )
               print(goal.model_dump_json(indent=2))
               continue

           if result and result.pending_question:
               human_input = input(f"{result.pending_question} ")
               goal = await client.resume_goal(
                   goal.id,
                   human_input=human_input,
               )
               print(goal.model_dump_json(indent=2))
               continue

           break


   if __name__ == "__main__":
       asyncio.run(main())

Optional integration hooks
--------------------------

The core example above works with HTTP registration and task dispatch. The same
agents can add optional integrations where the deployment needs them.

ROS 2 robot action
~~~~~~~~~~~~~~~~~~

Register a ROS 2 action as the implementation behind an EdgeFleet action. The
LLM still sees the JSON-schema tool; ROS 2 handles the robot-side execution.

.. code-block:: python

   from edgefleet import ActionPolicy
   from edgefleet.integrations.ros2 import ROS2ActionAdapter
   from lab_robot_interfaces.action import PickAndPlace


   def goal_factory(arguments):
       goal = PickAndPlace.Goal()
       goal.sample_id = arguments["sample_id"]
       goal.from_position = arguments["from_position"]
       goal.rack = arguments["rack"]
       goal.slot = arguments["slot"]
       goal.speed = arguments["speed"]
       return goal


   ros_move_sample = ROS2ActionAdapter(
       node_name="edgefleet_robot_arm",
       action_name="/pick_and_place",
       action_type=PickAndPlace,
       goal_factory=goal_factory,
       result_mapper=lambda result: {"status": result.status},
   ).as_action(
       name="move_sample",
       description="Move one sample through the ROS 2 robot controller.",
       input_schema={
           "type": "object",
           "properties": {
               "sample_id": {"type": "string"},
               "from_position": {"type": "string"},
               "rack": {"type": "string"},
               "slot": {"type": "string"},
               "speed": {"type": "string", "enum": ["slow", "normal"]},
           },
           "required": [
               "sample_id",
               "from_position",
               "rack",
               "slot",
               "speed",
           ],
           "additionalProperties": False,
       },
       policy=ActionPolicy.CONTROLLED,
   )

   actions.register(ros_move_sample)

MCP camera or instrument tools
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If camera capture or instrument access is already exposed through MCP, import
those MCP tools into the agent's action registry.

.. code-block:: python

   from edgefleet import ActionPolicy
   from edgefleet.integrations.mcp import MCPToolProvider


   await MCPToolProvider(
       "http://camera-gateway.local:9000/mcp",
       policy=ActionPolicy.SAFE,
   ).load_into(actions)

NATS task transport
~~~~~~~~~~~~~~~~~~~

Use NATS where direct HTTP is awkward, for example on intermittently connected
lab networks.

.. code-block:: python

   from edgefleet.integrations.nats import NATSTaskTransport


   transport = NATSTaskTransport(["nats://lab-gateway.local:4222"])
   await transport.connect()
   await transport.serve("robot-arm-agent", agent.execute)

A2A facade
~~~~~~~~~~

Expose an EdgeFleet agent to A2A-compatible systems without changing the core
agent implementation.

.. code-block:: python

   from edgefleet.integrations.a2a import mount_a2a


   app = agent.create_app()
   mount_a2a(app, agent)

LangGraph routing
~~~~~~~~~~~~~~~~~

Use a compiled LangGraph graph when capability-based routing is too simple.

.. code-block:: python

   from edgefleet import Orchestrator
   from edgefleet.routing import LangGraphRouter


   orchestrator = Orchestrator(
       router=LangGraphRouter(compiled_graph),
       token=os.getenv("EDGEFLEET_TOKEN"),
       edge_token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
   )

Operational notes
-----------------

For a real lab cell, treat EdgeFleet as the coordination layer:

* Use hardware controllers, ROS 2 action servers, PLCs, interlocks, and
  emergency stops for physical safety.
* Store orchestrator and agent state on durable media if goals must survive
  restarts.
* Keep approval prompts specific. Operators should see the exact action and
  arguments before approving.
* Use local models with reliable tool-calling behavior. Not every small local
  model will produce valid function calls consistently.
* Add audit logging around approvals and physical commands if the lab is
  regulated.
