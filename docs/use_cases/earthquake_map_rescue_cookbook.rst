Earthquake map-and-rescue robotics cookbook
===========================================

Scenario: earthquake survivor mapping and rescue
------------------------------------------------

A severe earthquake has damaged several city blocks. Roads are partially
blocked, buildings have unstable void spaces, indoor visibility is poor, and
the first hours of the response require fast mapping without putting human
responders into avoidable danger. The deployed robotic fleet contains flying
drones, ground crawlers, and excavators.

The mission starts as a map-and-rescue operation. Multiple drones and crawlers
are assigned to different sectors of the disaster area. Drones produce fast
aerial coverage, thermal observations, roof and street access maps, and
high-level hazard markers. Crawlers enter lower, tighter, or partially enclosed
areas where drones cannot safely fly. They inspect void spaces, listen for
survivors, capture close-range images, and refine the uncertainty in each
sector map.

The fleet is not trying to make autonomous medical decisions. It is collecting
observable evidence: motion, voice response, posture, visible injury category,
thermal signature, accessibility, local hazards, and whether a victim can
interact with a delivered kit. Those observations are converted into
human-reviewable triage categories such as ``critical_observed``,
``urgent_observed``, and ``stable_observed``. The category determines which
first-aid kit is proposed for delivery by a drone or crawler, but final rescue
priority and treatment decisions remain with qualified responders.

After enough of the site has been mapped, the system proposes excavation
missions. Excavators are deployed only after the rescue coordinator has a
sector map, victim locations, hazard notes, and an approved bounded excavation
step. The excavator edge agent can stage the machine or remove a specific
debris segment through deterministic controller calls, but those actions are
dangerous and must pause for explicit human approval.

EdgeFleet fits this scenario because the mission naturally separates into
local edge responsibilities:

* The incident-command gateway runs the orchestrator. It registers robots,
  stores sector results, routes tasks by target robot or skill, resumes paused
  approvals, and manages a persistent mission goal.
* A rescue coordinator agent runs on the command vehicle or gateway. It uses a
  local LLM to turn the incident commander's objective into bounded subtasks,
  delegate them to robot agents, summarize observations, and request approval
  before physical actions.
* Drone edge agents run on each drone or companion computer. They advertise
  aerial survey, victim observation, and first-aid delivery support
  capabilities.
* Crawler edge agents run on each ground robot. They advertise close inspection,
  void-space scanning, victim observation, and first-aid placement
  capabilities.
* Excavator edge agents run on each excavator gateway. They advertise machine
  status, debris-step evaluation, staging, and approved debris-removal actions.
* The action layer validates all physical action payloads against JSON Schema
  and enforces controlled or dangerous approval policy.
* Optional integration adapters can bridge these EdgeFleet actions to ROS 2
  actions, NATS messaging, MCP tools, A2A agent cards, or LangGraph workflows.

The LLM's role is coordination and reasoning over mission context. It can
summarize maps, compare uncertain observations, choose which agent should
inspect next, generate bounded tool calls, and produce responder-facing
briefings. It should not fly the drone, drive the crawler, control hydraulic
actuators, perform collision avoidance, replace emergency-stop logic, or make
clinical determinations.

Mission workflow
----------------

The normal mission loop is:

#. The incident commander creates a persistent goal: map the earthquake site,
   locate survivors, deliver first-aid kits where appropriate, and propose
   excavation steps for trapped survivors.
#. The orchestrator routes the goal task to the rescue coordinator agent.
#. The coordinator partitions the site into sectors and delegates aerial
   survey tasks to available drones.
#. Drones return map tiles, hazards, thermal observations, landing/drop-zone
   candidates, and rough victim observations.
#. The coordinator delegates close inspection or void-space scans to crawlers
   for sectors that have occlusions, weak confidence, or indoor/under-rubble
   observations.
#. Crawlers return close-range victim observations, accessibility, void
   stability notes, and possible first-aid placement routes.
#. The coordinator proposes first-aid delivery actions for victims whose
   observed condition and accessibility match available kits.
#. Drone and crawler first-aid actions are controlled actions. EdgeFleet
   validates the payload and pauses until a human approves.
#. Once mapping confidence is sufficient, the coordinator asks excavator agents
   to evaluate bounded debris-removal steps.
#. Excavator movement or debris removal is dangerous. EdgeFleet pauses with
   exact action arguments, and a human approves, rejects, or supplies updated
   instructions.
#. After each delivery or excavation step, drones and crawlers re-map the sector
   and the loop repeats until the persistent goal completes or command pauses
   the mission.

Data contracts used by the example
----------------------------------

The code below uses deliberately small payloads so the EdgeFleet boundary is
clear. Production deployments should replace the mock hardware classes with
validated robot drivers, sensor pipelines, and command interfaces.

.. list-table::
   :header-rows: 1
   :widths: 24 38 38

   * - Contract
     - Producer
     - Purpose
   * - ``sector_aerial_survey``
     - Drone agent
     - Produces coarse maps, hazards, possible victims, and first-aid drop
       zones for a sector.
   * - ``victim_observation``
     - Drone or crawler agent
     - Produces observable victim condition markers without claiming a medical
       diagnosis.
   * - ``sector_ground_survey``
     - Crawler agent
     - Produces close-range traversability, void-space, and victim access
       observations.
   * - ``evaluate_debris_removal_step``
     - Excavator agent
     - Checks whether a proposed debris-removal step is bounded, mapped, and
       ready for human review.
   * - ``drop_first_aid_kit``
     - Drone action
     - Controlled action that releases a kit at a specific coordinate.
   * - ``place_first_aid_kit``
     - Crawler action
     - Controlled action that places a kit near a reachable victim.
   * - ``stage_excavator`` and ``remove_debris_step``
     - Excavator actions
     - Controlled or dangerous actions routed to deterministic machine
       controllers after approval.

Complete Python programs
------------------------

The programs use environment variables so the same file can be deployed to
multiple robots. For example, ``drone_edge_agent.py`` can run as ``drone-01``
in sector A and as ``drone-02`` in sector B by changing
``EDGEFLEET_AGENT_ID``, ``EDGEFLEET_SECTOR_ID``, and ``EDGEFLEET_PORT``.

Incident-command orchestrator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Purpose
^^^^^^^

The orchestrator runs on the command vehicle, field server, or local disaster
recovery gateway. It is the durable mission coordination point. It stores
registered robot descriptors, task results, paused approval checkpoints, and
persistent goals. It does not directly operate a robot; it routes work to
agents and resumes tasks after human approvals.

.. code-block:: python

   # earthquake_orchestrator.py
   import os

   from edgefleet import JsonFileStore, Orchestrator


   orchestrator = Orchestrator(
       store=JsonFileStore("state/earthquake-orchestrator.json"),
       token=os.getenv("EDGEFLEET_TOKEN"),
       edge_token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
   )

   app = orchestrator.create_app()

Run it on the incident-command gateway:

.. code-block:: console

   $ uvicorn earthquake_orchestrator:app --host 0.0.0.0 --port 8000

Rescue coordinator agent
~~~~~~~~~~~~~~~~~~~~~~~~

Purpose
^^^^^^^

The rescue coordinator is the agentic supervisor for the mission. It receives
the incident commander's high-level objective, delegates bounded subtasks to
drones, crawlers, and excavators, compares results, and creates a concise
mission summary. It is the correct place for local LLM reasoning because it
works at the planning and coordination layer.

The coordinator should ask robot agents for observations and proposed actions.
It should not bypass action approval, generate raw motor commands, or claim a
medical diagnosis. When it wants a physical action, it delegates to the robot
agent that owns that action so the robot's local action layer can validate the
arguments and pause for approval.

.. code-block:: python

   # rescue_coordinator_agent.py
   import os

   from edgefleet import EdgeAgent, JsonFileRuntimeState, OpenAICompatibleLLM


   AGENT_ID = os.getenv("EDGEFLEET_AGENT_ID", "rescue-coordinator")
   PORT = int(os.getenv("EDGEFLEET_PORT", "8300"))
   PUBLIC_HOST = os.getenv("EDGEFLEET_PUBLIC_HOST", "rescue-gateway.local")
   ORCHESTRATOR_URL = os.getenv(
       "EDGEFLEET_ORCHESTRATOR_URL",
       "http://rescue-gateway.local:8000",
   )


   def make_llm() -> OpenAICompatibleLLM:
       return OpenAICompatibleLLM(
           model=os.getenv("EDGEFLEET_MODEL", "qwen3:1.7b"),
           base_url=os.getenv(
               "EDGEFLEET_LLM_URL",
               "http://127.0.0.1:11434/v1",
           ),
           api_key=os.getenv("EDGEFLEET_LLM_API_KEY", "local"),
           temperature=0.1,
       )


   agent = EdgeAgent(
       agent_id=AGENT_ID,
       name="Earthquake rescue coordinator",
       endpoint=f"http://{PUBLIC_HOST}:{PORT}",
       description=(
           "Coordinates earthquake mapping, survivor observation, first-aid "
           "delivery proposals, and excavation proposals."
       ),
       llm=make_llm(),
       state=JsonFileRuntimeState(f"state/{AGENT_ID}.json"),
       token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
       orchestrator_url=ORCHESTRATOR_URL,
       orchestrator_token=os.getenv("EDGEFLEET_TOKEN"),
       max_tool_rounds=8,
       system_prompt=(
           "You coordinate a disaster-response robot fleet. Use robots for "
           "bounded observations and guarded actions. Do not provide medical "
           "diagnoses, direct low-level robot control, or unsafe excavation "
           "instructions. Prefer explicit uncertainty and human approval."
       ),
   )

   agent.prompt_skill(
       "coordinate_map_and_rescue",
       description=(
           "Coordinate drones, crawlers, and excavators for an earthquake "
           "map-and-rescue mission."
       ),
       tags=["coordination", "llm", "rescue"],
       prompt_template="""
   Mission request:
   {input}

   Mission context:
   {context}

   Coordinate the mission using available delegate_task tools. Use the
   declared fleet IDs from the request or context.

   Required behavior:
   - Partition the earthquake site into sectors.
   - Ask drones for sector_aerial_survey in assigned sectors.
   - Ask crawlers for sector_ground_survey where aerial confidence is low,
     where void spaces exist, or where a victim may be reachable.
   - Ask drones or crawlers for victim_observation when a possible survivor is
     detected.
   - Propose first-aid delivery only from observable condition and
     accessibility evidence.
   - Delegate controlled first-aid delivery to the robot best positioned to
     perform it.
   - Ask excavators to evaluate_debris_removal_step only after mapped victim
     locations and hazards are available.
   - Delegate excavation actions only as bounded proposed steps that can pause
     for human approval.

   Return a compact mission summary with these sections:
   mission_state, sector_priorities, victims_observed, first_aid_plan,
   excavation_candidates, approvals_needed, and next_requests.
   """,
   )

   app = agent.create_app()

Run it on the command gateway:

.. code-block:: console

   $ EDGEFLEET_PORT=8300 \
     uvicorn rescue_coordinator_agent:app --host 0.0.0.0 --port 8300

Drone edge agent
~~~~~~~~~~~~~~~~

Purpose
^^^^^^^

Each drone edge agent runs on a drone companion computer or nearby control box.
It advertises fast aerial mapping, hazard observation, rough victim
observation, and controlled first-aid kit delivery. The drone is useful early
in the mission because it can map large areas quickly, identify blocked access
routes, find thermal signatures, and deliver light kits when ground access is
not yet available.

The drone's deterministic skills return sensor-derived facts. Its controlled
action, ``drop_first_aid_kit``, validates the victim ID, kit type, coordinate,
and drop altitude before asking for approval. The actual release call should be
implemented by a deterministic flight controller or payload controller, not by
the LLM.

.. code-block:: python

   # drone_edge_agent.py
   import os
   from datetime import UTC, datetime
   from typing import Any

   from edgefleet import (
       ActionPolicy,
       ActionRegistry,
       EdgeAgent,
       JsonFileRuntimeState,
       OpenAICompatibleLLM,
   )


   AGENT_ID = os.getenv("EDGEFLEET_AGENT_ID", "drone-01")
   SECTOR_ID = os.getenv("EDGEFLEET_SECTOR_ID", "sector-a")
   PORT = int(os.getenv("EDGEFLEET_PORT", "8311"))
   PUBLIC_HOST = os.getenv("EDGEFLEET_PUBLIC_HOST", f"{AGENT_ID}.local")
   ORCHESTRATOR_URL = os.getenv(
       "EDGEFLEET_ORCHESTRATOR_URL",
       "http://rescue-gateway.local:8000",
   )


   def utc_timestamp() -> str:
       return datetime.now(UTC).isoformat()


   def make_llm() -> OpenAICompatibleLLM:
       return OpenAICompatibleLLM(
           model=os.getenv("EDGEFLEET_MODEL", "qwen3:1.7b"),
           base_url=os.getenv(
               "EDGEFLEET_LLM_URL",
               "http://127.0.0.1:11434/v1",
           ),
           api_key=os.getenv("EDGEFLEET_LLM_API_KEY", "local"),
           temperature=0.1,
       )


   class DroneHardware:
       """Replace this mock with real drone, camera, and payload adapters."""

       def __init__(self, robot_id: str) -> None:
           self.robot_id = robot_id

       def capture_map_tile(self, sector_id: str) -> dict[str, Any]:
           return {
               "sector_id": sector_id,
               "map_tile_id": f"{sector_id}-aerial-tile-001",
               "coverage_pct": 72,
               "confidence": 0.76,
               "hazards": [
                   {
                       "type": "unstable_roof",
                       "coordinates": [23.78001, 90.41011],
                       "severity": "high",
                   },
                   {
                       "type": "blocked_road",
                       "coordinates": [23.77981, 90.41002],
                       "severity": "medium",
                   },
               ],
               "drop_zones": [
                   {
                       "id": "dz-a1",
                       "coordinates": [23.78008, 90.41020],
                       "radius_m": 3.0,
                       "risk": "medium",
                   }
               ],
           }

       def detect_possible_victims(self, sector_id: str) -> list[dict[str, Any]]:
           return [
               {
                   "victim_id": f"{sector_id}-victim-01",
                   "coordinates": [23.78012, 90.41024],
                   "observation_source": "thermal_and_motion",
                   "condition_observed": "urgent_observed",
                   "confidence": 0.68,
                   "visible_constraints": ["partial_debris_cover"],
                   "recommended_kit": "trauma_basic",
               }
           ]

       def release_aid_kit(
           self,
           *,
           victim_id: str,
           kit_type: str,
           coordinates: list[float],
           altitude_m: float,
       ) -> dict[str, Any]:
           return {
               "robot_id": self.robot_id,
               "action": "drop_first_aid_kit",
               "victim_id": victim_id,
               "kit_type": kit_type,
               "coordinates": coordinates,
               "altitude_m": altitude_m,
               "status": "release_command_sent_to_payload_controller",
               "completed_at": utc_timestamp(),
           }


   hardware = DroneHardware(AGENT_ID)
   actions = ActionRegistry()


   @actions.action(
       "drop_first_aid_kit",
       description=(
           "Release a lightweight first-aid kit at a mapped coordinate. This "
           "must only be called after route, altitude, weather, and bystander "
           "risk checks have passed."
       ),
       policy=ActionPolicy.CONTROLLED,
       input_schema={
           "type": "object",
           "properties": {
               "victim_id": {"type": "string"},
               "kit_type": {
                   "type": "string",
                   "enum": [
                       "trauma_basic",
                       "bleeding_control",
                       "water_blanket",
                       "communication_beacon",
                   ],
               },
               "coordinates": {
                   "type": "array",
                   "items": {"type": "number"},
                   "minItems": 2,
                   "maxItems": 2,
               },
               "altitude_m": {
                   "type": "number",
                   "minimum": 1.0,
                   "maximum": 12.0,
               },
           },
           "required": [
               "victim_id",
               "kit_type",
               "coordinates",
               "altitude_m",
           ],
           "additionalProperties": False,
       },
   )
   async def drop_first_aid_kit(
       victim_id: str,
       kit_type: str,
       coordinates: list[float],
       altitude_m: float,
   ) -> dict[str, Any]:
       return hardware.release_aid_kit(
           victim_id=victim_id,
           kit_type=kit_type,
           coordinates=coordinates,
           altitude_m=altitude_m,
       )


   agent = EdgeAgent(
       agent_id=AGENT_ID,
       name=f"Disaster response drone {AGENT_ID}",
       endpoint=f"http://{PUBLIC_HOST}:{PORT}",
       description=(
           "Aerial mapping, thermal observation, victim spotting, and "
           "controlled first-aid kit delivery."
       ),
       llm=make_llm(),
       actions=actions,
       state=JsonFileRuntimeState(f"state/{AGENT_ID}.json"),
       token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
       orchestrator_url=ORCHESTRATOR_URL,
       orchestrator_token=os.getenv("EDGEFLEET_TOKEN"),
       max_tool_rounds=4,
       system_prompt=(
           "You are a disaster-response drone edge agent. Report observable "
           "facts, uncertainty, and hazards. Do not fly the drone directly or "
           "make medical diagnoses. Use guarded tools for physical actions."
       ),
   )


   @agent.skill(
       "sector_aerial_survey",
       description="Map a sector from the air and report hazards and possible victims.",
       tags=["drone", "mapping", "deterministic"],
       input_schema={
           "type": "object",
           "properties": {"sector_id": {"type": "string"}},
           "required": ["sector_id"],
       },
   )
   async def sector_aerial_survey(task) -> dict[str, Any]:
       sector_id = task.input.get("sector_id", SECTOR_ID)
       map_tile = hardware.capture_map_tile(sector_id)
       victims = hardware.detect_possible_victims(sector_id)
       return {
           "robot_id": AGENT_ID,
           "sector_id": sector_id,
           "observed_at": utc_timestamp(),
           "map_tile": map_tile,
           "possible_victims": victims,
           "recommended_next_steps": [
               "send_crawler_for_close_inspection",
               "review_drop_zone_before_aid_delivery",
           ],
       }


   @agent.skill(
       "victim_observation",
       description="Return drone-observable condition markers for a possible survivor.",
       tags=["drone", "victim-observation", "deterministic"],
   )
   async def victim_observation(task) -> dict[str, Any]:
       sector_id = task.input.get("sector_id", SECTOR_ID)
       victim_id = task.input.get("victim_id", f"{sector_id}-victim-01")
       victims = hardware.detect_possible_victims(sector_id)
       selected = next(
           (victim for victim in victims if victim["victim_id"] == victim_id),
           victims[0],
       )
       return {
           "robot_id": AGENT_ID,
           "victim_id": selected["victim_id"],
           "observed_at": utc_timestamp(),
           "condition_observed": selected["condition_observed"],
           "confidence": selected["confidence"],
           "medical_diagnosis": None,
           "evidence": [
               selected["observation_source"],
               *selected["visible_constraints"],
           ],
           "recommended_kit": selected["recommended_kit"],
       }


   agent.prompt_skill(
       "drone_rescue_support",
       description=(
           "Use drone observations and guarded actions to support a bounded "
           "rescue task."
       ),
       tags=["drone", "llm", "actions"],
       prompt_template="""
   Drone rescue support request:
   {input}

   Context:
   {context}

   Use deterministic survey facts when needed. If a first-aid kit should be
   delivered, call drop_first_aid_kit with exact victim_id, kit_type,
   coordinates, and altitude_m. Do not call the tool unless the requested
   payload is bounded and suitable for human approval.
   """,
   )

   app = agent.create_app()

Run two drones from the same program:

.. code-block:: console

   $ EDGEFLEET_AGENT_ID=drone-01 EDGEFLEET_SECTOR_ID=sector-a \
     EDGEFLEET_PUBLIC_HOST=drone-01.local EDGEFLEET_PORT=8311 \
     uvicorn drone_edge_agent:app --host 0.0.0.0 --port 8311

   $ EDGEFLEET_AGENT_ID=drone-02 EDGEFLEET_SECTOR_ID=sector-b \
     EDGEFLEET_PUBLIC_HOST=drone-02.local EDGEFLEET_PORT=8312 \
     uvicorn drone_edge_agent:app --host 0.0.0.0 --port 8312

Crawler edge agent
~~~~~~~~~~~~~~~~~~

Purpose
^^^^^^^

Each crawler edge agent runs on a ground robot. Crawlers are slower than
drones, but they can move under smoke, around rubble, and into void spaces
where aerial views are blocked. They improve map confidence, inspect possible
survivors at close range, relay audio, and place first-aid kits without
dropping them from altitude.

The crawler's deterministic skills should use local navigation, lidar, depth
cameras, microphones, gas sensors, and thermal sensors. Its
``place_first_aid_kit`` action is controlled because it moves near a victim and
places an object in the environment. In a real robot, this action should call a
validated navigation and manipulator stack.

.. code-block:: python

   # crawler_edge_agent.py
   import os
   from datetime import UTC, datetime
   from typing import Any

   from edgefleet import (
       ActionPolicy,
       ActionRegistry,
       EdgeAgent,
       JsonFileRuntimeState,
       OpenAICompatibleLLM,
   )


   AGENT_ID = os.getenv("EDGEFLEET_AGENT_ID", "crawler-01")
   SECTOR_ID = os.getenv("EDGEFLEET_SECTOR_ID", "sector-a")
   PORT = int(os.getenv("EDGEFLEET_PORT", "8321"))
   PUBLIC_HOST = os.getenv("EDGEFLEET_PUBLIC_HOST", f"{AGENT_ID}.local")
   ORCHESTRATOR_URL = os.getenv(
       "EDGEFLEET_ORCHESTRATOR_URL",
       "http://rescue-gateway.local:8000",
   )


   def utc_timestamp() -> str:
       return datetime.now(UTC).isoformat()


   def make_llm() -> OpenAICompatibleLLM:
       return OpenAICompatibleLLM(
           model=os.getenv("EDGEFLEET_MODEL", "qwen3:1.7b"),
           base_url=os.getenv(
               "EDGEFLEET_LLM_URL",
               "http://127.0.0.1:11434/v1",
           ),
           api_key=os.getenv("EDGEFLEET_LLM_API_KEY", "local"),
           temperature=0.1,
       )


   class CrawlerHardware:
       """Replace this mock with navigation, sensor, and manipulator adapters."""

       def __init__(self, robot_id: str) -> None:
           self.robot_id = robot_id

       def scan_sector(self, sector_id: str) -> dict[str, Any]:
           return {
               "sector_id": sector_id,
               "traversable_paths": [
                   {
                       "path_id": f"{sector_id}-path-01",
                       "clearance_m": 0.7,
                       "slope_deg": 8,
                       "risk": "medium",
                   }
               ],
               "void_spaces": [
                   {
                       "void_id": f"{sector_id}-void-01",
                       "stability": "unknown",
                       "gas_ppm": 12,
                       "thermal_signature": True,
                   }
               ],
               "map_confidence_delta": 0.18,
           }

       def observe_victim(self, victim_id: str) -> dict[str, Any]:
           return {
               "victim_id": victim_id,
               "condition_observed": "critical_observed",
               "confidence": 0.74,
               "responsive_to_audio": True,
               "visible_constraints": [
                   "leg_obstructed",
                   "dust_exposure",
               ],
               "reachable_by_crawler": True,
               "recommended_kit": "bleeding_control",
           }

       def place_kit(
           self,
           *,
           victim_id: str,
           kit_type: str,
           approach_path_id: str,
           standoff_m: float,
       ) -> dict[str, Any]:
           return {
               "robot_id": self.robot_id,
               "action": "place_first_aid_kit",
               "victim_id": victim_id,
               "kit_type": kit_type,
               "approach_path_id": approach_path_id,
               "standoff_m": standoff_m,
               "status": "placement_command_sent_to_robot_controller",
               "completed_at": utc_timestamp(),
           }


   hardware = CrawlerHardware(AGENT_ID)
   actions = ActionRegistry()


   @actions.action(
       "place_first_aid_kit",
       description=(
           "Navigate along a reviewed approach path and place a first-aid kit "
           "within reach of a possible survivor."
       ),
       policy=ActionPolicy.CONTROLLED,
       input_schema={
           "type": "object",
           "properties": {
               "victim_id": {"type": "string"},
               "kit_type": {
                   "type": "string",
                   "enum": [
                       "trauma_basic",
                       "bleeding_control",
                       "water_blanket",
                       "communication_beacon",
                   ],
               },
               "approach_path_id": {"type": "string"},
               "standoff_m": {
                   "type": "number",
                   "minimum": 0.5,
                   "maximum": 5.0,
               },
           },
           "required": [
               "victim_id",
               "kit_type",
               "approach_path_id",
               "standoff_m",
           ],
           "additionalProperties": False,
       },
   )
   async def place_first_aid_kit(
       victim_id: str,
       kit_type: str,
       approach_path_id: str,
       standoff_m: float,
   ) -> dict[str, Any]:
       return hardware.place_kit(
           victim_id=victim_id,
           kit_type=kit_type,
           approach_path_id=approach_path_id,
           standoff_m=standoff_m,
       )


   agent = EdgeAgent(
       agent_id=AGENT_ID,
       name=f"Disaster response crawler {AGENT_ID}",
       endpoint=f"http://{PUBLIC_HOST}:{PORT}",
       description=(
           "Ground inspection, void-space scanning, close victim observation, "
           "and controlled first-aid placement."
       ),
       llm=make_llm(),
       actions=actions,
       state=JsonFileRuntimeState(f"state/{AGENT_ID}.json"),
       token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
       orchestrator_url=ORCHESTRATOR_URL,
       orchestrator_token=os.getenv("EDGEFLEET_TOKEN"),
       max_tool_rounds=4,
       system_prompt=(
           "You are a disaster-response crawler edge agent. Report sensor "
           "observations and uncertainty. Do not make medical diagnoses or "
           "unsafe navigation claims. Use guarded tools for physical actions."
       ),
   )


   @agent.skill(
       "sector_ground_survey",
       description="Inspect a sector from the ground and report traversability.",
       tags=["crawler", "mapping", "deterministic"],
       input_schema={
           "type": "object",
           "properties": {"sector_id": {"type": "string"}},
           "required": ["sector_id"],
       },
   )
   async def sector_ground_survey(task) -> dict[str, Any]:
       sector_id = task.input.get("sector_id", SECTOR_ID)
       scan = hardware.scan_sector(sector_id)
       return {
           "robot_id": AGENT_ID,
           "sector_id": sector_id,
           "observed_at": utc_timestamp(),
           "ground_scan": scan,
           "recommended_next_steps": [
               "request_structural_review_for_void_space",
               "observe_possible_victim_from_standoff",
           ],
       }


   @agent.skill(
       "victim_observation",
       description="Return close-range observed condition markers.",
       tags=["crawler", "victim-observation", "deterministic"],
   )
   async def victim_observation(task) -> dict[str, Any]:
       victim_id = task.input.get(
           "victim_id",
           f"{task.input.get('sector_id', SECTOR_ID)}-victim-01",
       )
       observation = hardware.observe_victim(victim_id)
       return {
           "robot_id": AGENT_ID,
           "observed_at": utc_timestamp(),
           "medical_diagnosis": None,
           **observation,
       }


   agent.prompt_skill(
       "crawler_rescue_support",
       description=(
           "Use close-range crawler observations and guarded actions to "
           "support a bounded rescue task."
       ),
       tags=["crawler", "llm", "actions"],
       prompt_template="""
   Crawler rescue support request:
   {input}

   Context:
   {context}

   Use sector_ground_survey and victim_observation facts when needed. If a
   first-aid kit should be placed, call place_first_aid_kit with exact
   victim_id, kit_type, approach_path_id, and standoff_m. Do not call the tool
   unless the route and payload are explicit enough for human approval.
   """,
   )

   app = agent.create_app()

Run two crawlers from the same program:

.. code-block:: console

   $ EDGEFLEET_AGENT_ID=crawler-01 EDGEFLEET_SECTOR_ID=sector-a \
     EDGEFLEET_PUBLIC_HOST=crawler-01.local EDGEFLEET_PORT=8321 \
     uvicorn crawler_edge_agent:app --host 0.0.0.0 --port 8321

   $ EDGEFLEET_AGENT_ID=crawler-02 EDGEFLEET_SECTOR_ID=sector-c \
     EDGEFLEET_PUBLIC_HOST=crawler-02.local EDGEFLEET_PORT=8322 \
     uvicorn crawler_edge_agent:app --host 0.0.0.0 --port 8322

Excavator edge agent
~~~~~~~~~~~~~~~~~~~~

Purpose
^^^^^^^

Each excavator edge agent runs on a heavy-machine gateway. Excavators enter
the mission only after drones and crawlers have created enough map evidence to
identify a bounded debris-removal step. The excavator agent advertises status
and step-evaluation skills, then exposes guarded actions for staging and
removing debris.

The excavator agent is intentionally conservative. ``stage_excavator`` is a
controlled action because it moves equipment into position. ``remove_debris_step``
is a dangerous action because it can change the collapse environment. Both
actions should call deterministic machine controllers, geofencing, interlocks,
and operator consoles in a real deployment.

.. code-block:: python

   # excavator_edge_agent.py
   import os
   from datetime import UTC, datetime
   from typing import Any

   from edgefleet import (
       ActionPolicy,
       ActionRegistry,
       EdgeAgent,
       JsonFileRuntimeState,
       OpenAICompatibleLLM,
   )


   AGENT_ID = os.getenv("EDGEFLEET_AGENT_ID", "excavator-01")
   SECTOR_ID = os.getenv("EDGEFLEET_SECTOR_ID", "sector-a")
   PORT = int(os.getenv("EDGEFLEET_PORT", "8331"))
   PUBLIC_HOST = os.getenv("EDGEFLEET_PUBLIC_HOST", f"{AGENT_ID}.local")
   ORCHESTRATOR_URL = os.getenv(
       "EDGEFLEET_ORCHESTRATOR_URL",
       "http://rescue-gateway.local:8000",
   )


   def utc_timestamp() -> str:
       return datetime.now(UTC).isoformat()


   def make_llm() -> OpenAICompatibleLLM:
       return OpenAICompatibleLLM(
           model=os.getenv("EDGEFLEET_MODEL", "qwen3:1.7b"),
           base_url=os.getenv(
               "EDGEFLEET_LLM_URL",
               "http://127.0.0.1:11434/v1",
           ),
           api_key=os.getenv("EDGEFLEET_LLM_API_KEY", "local"),
           temperature=0.1,
       )


   class ExcavatorController:
       """Replace this mock with a validated heavy-equipment control gateway."""

       def __init__(self, robot_id: str) -> None:
           self.robot_id = robot_id

       def status(self) -> dict[str, Any]:
           return {
               "robot_id": self.robot_id,
               "engine_state": "ready",
               "operator_console_connected": True,
               "geofence_active": True,
               "emergency_stop_ok": True,
               "max_bucket_load_kg": 400,
           }

       def evaluate_step(
           self,
           *,
           sector_id: str,
           debris_segment_id: str,
           victim_standoff_m: float,
       ) -> dict[str, Any]:
           ready = victim_standoff_m >= 3.0
           return {
               "sector_id": sector_id,
               "debris_segment_id": debris_segment_id,
               "victim_standoff_m": victim_standoff_m,
               "bounded_step": True,
               "requires_structural_review": True,
               "machine_ready": self.status(),
               "ready_for_human_review": ready,
               "blocking_reasons": [] if ready else ["victim_standoff_too_low"],
           }

       def stage(self, *, sector_id: str, staging_zone_id: str) -> dict[str, Any]:
           return {
               "robot_id": self.robot_id,
               "action": "stage_excavator",
               "sector_id": sector_id,
               "staging_zone_id": staging_zone_id,
               "status": "stage_command_sent_to_machine_gateway",
               "completed_at": utc_timestamp(),
           }

       def remove_debris(
           self,
           *,
           sector_id: str,
           debris_segment_id: str,
           pass_count: int,
           max_bucket_load_kg: float,
       ) -> dict[str, Any]:
           return {
               "robot_id": self.robot_id,
               "action": "remove_debris_step",
               "sector_id": sector_id,
               "debris_segment_id": debris_segment_id,
               "pass_count": pass_count,
               "max_bucket_load_kg": max_bucket_load_kg,
               "status": "bounded_debris_command_sent_to_machine_gateway",
               "completed_at": utc_timestamp(),
           }


   controller = ExcavatorController(AGENT_ID)
   actions = ActionRegistry()


   @actions.action(
       "stage_excavator",
       description="Move the excavator to a reviewed staging zone.",
       policy=ActionPolicy.CONTROLLED,
       input_schema={
           "type": "object",
           "properties": {
               "sector_id": {"type": "string"},
               "staging_zone_id": {"type": "string"},
           },
           "required": ["sector_id", "staging_zone_id"],
           "additionalProperties": False,
       },
   )
   async def stage_excavator(
       sector_id: str,
       staging_zone_id: str,
   ) -> dict[str, Any]:
       return controller.stage(
           sector_id=sector_id,
           staging_zone_id=staging_zone_id,
       )


   @actions.action(
       "remove_debris_step",
       description=(
           "Execute one bounded debris-removal step after mapping, structural "
           "review, responder approval, and machine safety checks."
       ),
       policy=ActionPolicy.DANGEROUS,
       input_schema={
           "type": "object",
           "properties": {
               "sector_id": {"type": "string"},
               "debris_segment_id": {"type": "string"},
               "pass_count": {"type": "integer", "minimum": 1, "maximum": 3},
               "max_bucket_load_kg": {
                   "type": "number",
                   "minimum": 10,
                   "maximum": 400,
               },
           },
           "required": [
               "sector_id",
               "debris_segment_id",
               "pass_count",
               "max_bucket_load_kg",
           ],
           "additionalProperties": False,
       },
   )
   async def remove_debris_step(
       sector_id: str,
       debris_segment_id: str,
       pass_count: int,
       max_bucket_load_kg: float,
   ) -> dict[str, Any]:
       return controller.remove_debris(
           sector_id=sector_id,
           debris_segment_id=debris_segment_id,
           pass_count=pass_count,
           max_bucket_load_kg=max_bucket_load_kg,
       )


   agent = EdgeAgent(
       agent_id=AGENT_ID,
       name=f"Disaster response excavator {AGENT_ID}",
       endpoint=f"http://{PUBLIC_HOST}:{PORT}",
       description=(
           "Heavy-equipment status, bounded debris-step evaluation, staging, "
           "and approval-gated debris removal."
       ),
       llm=make_llm(),
       actions=actions,
       state=JsonFileRuntimeState(f"state/{AGENT_ID}.json"),
       token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
       orchestrator_url=ORCHESTRATOR_URL,
       orchestrator_token=os.getenv("EDGEFLEET_TOKEN"),
       max_tool_rounds=4,
       system_prompt=(
           "You are an excavator edge agent. Be conservative. Do not create "
           "raw hydraulic commands. Only use guarded actions with explicit, "
           "bounded arguments suitable for human approval."
       ),
   )


   @agent.skill(
       "excavator_status",
       description="Return current machine, geofence, and safety-gateway status.",
       tags=["excavator", "status", "deterministic"],
   )
   async def excavator_status(task) -> dict[str, Any]:
       return {
           "observed_at": utc_timestamp(),
           "status": controller.status(),
       }


   @agent.skill(
       "evaluate_debris_removal_step",
       description="Evaluate whether a proposed debris-removal step is bounded.",
       tags=["excavator", "planning", "deterministic"],
       input_schema={
           "type": "object",
           "properties": {
               "sector_id": {"type": "string"},
               "debris_segment_id": {"type": "string"},
               "victim_standoff_m": {"type": "number"},
           },
           "required": [
               "sector_id",
               "debris_segment_id",
               "victim_standoff_m",
           ],
       },
   )
   async def evaluate_debris_removal_step(task) -> dict[str, Any]:
       return controller.evaluate_step(
           sector_id=task.input.get("sector_id", SECTOR_ID),
           debris_segment_id=task.input["debris_segment_id"],
           victim_standoff_m=float(task.input["victim_standoff_m"]),
       )


   agent.prompt_skill(
       "excavation_rescue_step",
       description="Prepare or execute a bounded, approval-gated excavation step.",
       tags=["excavator", "llm", "actions"],
       prompt_template="""
   Excavation support request:
   {input}

   Context:
   {context}

   Check excavator_status and evaluate_debris_removal_step before physical
   actions. Call stage_excavator only for an explicit sector and staging zone.
   Call remove_debris_step only when the step is bounded, reviewed, and ready
   for human approval. Never create raw actuator commands.
   """,
   )

   app = agent.create_app()

Run an excavator edge gateway:

.. code-block:: console

   $ EDGEFLEET_AGENT_ID=excavator-01 EDGEFLEET_SECTOR_ID=sector-a \
     EDGEFLEET_PUBLIC_HOST=excavator-01.local EDGEFLEET_PORT=8331 \
     uvicorn excavator_edge_agent:app --host 0.0.0.0 --port 8331

Incident commander client
~~~~~~~~~~~~~~~~~~~~~~~~~

Purpose
^^^^^^^

The incident commander client creates the persistent mission goal. It gives
the coordinator the incident objective, the sector list, the robot fleet, and
the mission policy. The client also shows how a human resumes a paused goal
after inspecting the exact pending action.

.. code-block:: python

   # incident_commander_client.py
   import asyncio
   import os
   from pprint import pprint

   from edgefleet import (
       EdgeFleetClient,
       ReasoningConfig,
       ReasoningMode,
       TaskRequest,
   )


   ORCHESTRATOR_URL = os.getenv(
       "EDGEFLEET_ORCHESTRATOR_URL",
       "http://rescue-gateway.local:8000",
   )


   async def main() -> None:
       client = EdgeFleetClient(
           ORCHESTRATOR_URL,
           token=os.getenv("EDGEFLEET_TOKEN"),
           timeout=600,
       )

       task = TaskRequest(
           target_agent="rescue-coordinator",
           skill="coordinate_map_and_rescue",
           input={
               "incident": "earthquake",
               "mission": (
                   "Map the affected site, locate survivors, deliver "
                   "appropriate first-aid kits based on observed condition and "
                   "accessibility, and propose bounded excavation steps for "
                   "trapped survivors."
               ),
               "site": {
                   "name": "north-market-block",
                   "sectors": ["sector-a", "sector-b", "sector-c"],
                   "known_hazards": [
                       "aftershock_risk",
                       "gas_leak_reports",
                       "unstable_masonry",
                   ],
               },
               "fleet": {
                   "drones": ["drone-01", "drone-02"],
                   "crawlers": ["crawler-01", "crawler-02"],
                   "excavators": ["excavator-01"],
               },
               "first_aid_policy": {
                   "critical_observed": "bleeding_control",
                   "urgent_observed": "trauma_basic",
                   "stable_observed": "water_blanket",
                   "unknown_observed": "communication_beacon",
               },
               "approval_policy": {
                   "first_aid_delivery": "human_approval_required",
                   "excavator_staging": "human_approval_required",
                   "debris_removal": "human_approval_required",
               },
           },
           context={
               "incident_id": "eq-north-market-001",
               "max_mapping_rounds": 4,
               "minimum_mapping_confidence_for_excavation": 0.80,
               "command_role": "incident_commander",
           },
           conversation_id="eq-north-market-001",
           allow_actions=True,
           reasoning=ReasoningConfig(
               mode=ReasoningMode.PLAN_EXECUTE,
               auto_delegate=True,
               max_delegation_depth=3,
               human_approval=True,
               memory=True,
               reasoning_summary=True,
           ),
       )

       goal = await client.create_goal(
           objective=(
               "Complete the earthquake map-and-rescue mission for "
               "north-market-block."
           ),
           task=task,
       )

       print(f"goal_id={goal.id}")
       print(f"state={goal.state}")
       pprint(goal.result.model_dump(mode="json") if goal.result else None)

       if goal.result and goal.result.pending_approvals:
           print("\nPending approvals:")
           for approval in goal.result.pending_approvals:
               pprint(approval.model_dump(mode="json"))

           approved = {
               approval.action
               for approval in goal.result.pending_approvals
               if approval.policy in {"controlled", "dangerous"}
           }

           resumed = await client.resume_goal(
               goal.id,
               approved_actions=approved,
           )
           print("\nAfter approval:")
           print(f"state={resumed.state}")
           pprint(
               resumed.result.model_dump(mode="json")
               if resumed.result
               else None
           )


   if __name__ == "__main__":
       asyncio.run(main())

Run the client from the command gateway or incident-command laptop:

.. code-block:: console

   $ python incident_commander_client.py

Integration notes
-----------------

The example keeps robot drivers as small Python classes so the EdgeFleet
interfaces are visible. In a real deployment, those classes are the correct
places to connect to validated middleware:

* Drone map capture and payload release can call vendor SDKs, ROS 2 actions, or
  a flight-controller gateway.
* Crawler navigation and kit placement can call ROS 2 navigation and
  manipulator actions.
* Excavator staging and debris removal can call a machine-control gateway that
  enforces geofencing, interlocks, operator presence, and emergency stops.
* NATS can carry tasks across intermittent field networks while EdgeFleet still
  owns task models and approvals.
* MCP can expose existing GIS, sensor, inventory, or responder tools to local
  agents without adding those tools to EdgeFleet core.
