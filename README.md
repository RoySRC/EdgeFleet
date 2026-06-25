# EdgeFleet

EdgeFleet is a Python package for coordinating local-LLM agents running on
edge devices. It provides one task API while keeping inference, networking,
and physical-device control replaceable.

The package includes:

- A FastAPI orchestrator with skill-based routing.
- An edge-agent runtime for Python skills and local LLMs.
- An OpenAI-compatible inference adapter for llama.cpp, Ollama, and vLLM.
- A guarded action registry for sensors, actuators, and robot commands.
- Optional MCP tool import, NATS transport, LangGraph routing, and ROS 2
  action adapters.
- Bearer-token authentication and Docker deployment examples.
- Composable reasoning modes, reflection, memory, retrieval, delegation,
  approval conversations, and persistent resumable goals.

## Architecture

```text
Application
    |
    | POST /v1/tasks
    v
EdgeFleet orchestrator
    |
    | route by skill, target, or LangGraph policy
    v
Edge agent ----> local llama.cpp / Ollama
    |
    +----> Python action
    +----> MCP tool
    +----> ROS 2 action --> MoveIt 2 --> ros2_control --> hardware
```

ROS 2, MoveIt, Zenoh, NATS, and inference servers are separate runtimes.
EdgeFleet integrates them but does not vendor them into one process. This is
intentional: real-time robot control must remain outside the LLM process.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
```

Install optional integrations as required:

```bash
pip install -e '.[mcp,nats,langgraph,a2a]'
```

`rclpy` is installed by ROS 2 rather than PyPI. Source the ROS environment
before starting an agent that uses the ROS 2 adapter.

## Run locally

Start an OpenAI-compatible local model. For Ollama:

```bash
ollama pull qwen3:1.7b
ollama serve
```

Start the orchestrator:

```bash
export EDGEFLEET_TOKEN=development-secret
export EDGEFLEET_EDGE_TOKEN=edge-secret
edgefleet orchestrator --port 8000
```

Start the example edge agent in a second terminal:

```bash
export EDGEFLEET_TOKEN=development-secret
export EDGEFLEET_EDGE_TOKEN=edge-secret
export EDGEFLEET_ORCHESTRATOR_URL=http://127.0.0.1:8000
edgefleet agent --factory examples.edge_agent:create_agent --port 8100
```

Run the example client:

```bash
export EDGEFLEET_TOKEN=development-secret
python examples/client.py
```

OpenAPI documentation is available at
`http://127.0.0.1:8000/docs`.

## Public Python API

```python
from edgefleet import EdgeFleetClient

client = EdgeFleetClient(
    "http://orchestrator.local:8000",
    token="shared-or-user-token",
)

result = await client.submit(
    {"part": "A-17"},
    skill="inspect_part",
    target_agent=None,
)
```

## Reasoning strategies

Reasoning is configured per task. Deterministic Python skill handlers still
bypass the LLM.

```python
from edgefleet import ReasoningConfig, ReasoningMode

result = await client.submit(
    "Diagnose intermittent actuator vibration",
    skill="diagnose",
    conversation_id="robot-7-maintenance",
    context={"robot": "robot-7", "shift": "night"},
    reasoning=ReasoningConfig(
        mode=ReasoningMode.PLAN_EXECUTE,
        reflection=True,
        reasoning_summary=True,
        memory=True,
        retrieval=True,
        auto_delegate=True,
        human_approval=True,
    ),
)
```

Available primary modes:

| Mode | Behavior |
|---|---|
| `direct` | Normal prompt and structured tool-use loop |
| `plan_execute` | Generates a structured plan, then executes with tools |
| `self_consistency` | Produces multiple candidates and judges them |
| `tree_search` | Explores and selects branches over bounded depths |
| `graph_search` | Generates a proposal/dependency graph and synthesizes a route |
| `debate` | Runs local persona debate or delegates rounds to named agents |

Optional capabilities can be combined with any primary mode:

- `reflection`: critique and revise the produced answer.
- `reasoning_summary`: record a concise decision summary in the task trace.
- `memory`: load and append conversation messages using `conversation_id`.
- `retrieval`: inject locally retrieved documents.
- `auto_delegate`: expose the bounded `delegate_task` tool.
- `human_approval`: expose `request_human_input` and pause for a response.

`reasoning_summary` intentionally stores a concise decision summary, not
hidden token-by-token chain-of-thought.

### Self-consistency, tree search, and debate

```python
ReasoningConfig(
    mode=ReasoningMode.SELF_CONSISTENCY,
    samples=4,
)

ReasoningConfig(
    mode=ReasoningMode.TREE_SEARCH,
    branches=3,
    depth=2,
)

ReasoningConfig(
    mode=ReasoningMode.DEBATE,
    debate_agents=["vision-edge", "safety-edge"],
    debate_rounds=2,
)
```

When `debate_agents` is empty, debate uses local personas on the same LLM.
Named debate agents communicate through the orchestrator.

## Prompt templates and dynamic context

Register an LLM-backed skill without a Python handler:

```python
agent.prompt_skill(
    "diagnose",
    description="Diagnose device faults",
    prompt_template=(
        "Diagnose {input}.\n"
        "Runtime context: {context}\n"
        "Metadata: {metadata}\n"
        "Return checks, evidence, and safe next actions."
    ),
)
```

Supported template variables are `input`, `context`, `metadata`, `skill`,
`conversation_id`, and `goal_id`. Task context and metadata are also added to
the system context, so they remain available without a custom template.

## Conversation memory and retrieval

```python
from edgefleet import Document, InMemoryRetriever

retriever = InMemoryRetriever([
    Document(
        id="ax7-manual",
        text="AX-7 maximum continuous temperature is 70 Celsius.",
        metadata={"source": "service manual"},
    )
])

agent = EdgeAgent(
    ...,
    retriever=retriever,
)
```

The built-in retriever is a dependency-free TF-IDF implementation intended
for small local document sets. Replace the `Retriever` interface with a vector
database adapter for larger collections.

Conversation memory and paused reasoning checkpoints use the configured agent
runtime state:

```python
from edgefleet import JsonFileRuntimeState

agent = EdgeAgent(
    ...,
    state=JsonFileRuntimeState("/var/lib/edgefleet/agent.json"),
)
```

## Human approval and resumable execution

Controlled and dangerous tool calls return `waiting_approval` instead of
failing:

```python
result = await client.submit(
    "Move the gripper to the pickup pose",
    allow_actions=True,
    reasoning=ReasoningConfig(human_approval=True),
)

if result.state == "waiting_approval":
    result = await client.resume(
        result.task_id,
        approved_actions={"move_gripper"},
    )
```

An agent can also call `request_human_input`. The task then returns
`waiting_input`:

```python
result = await client.resume(
    result.task_id,
    human_input="Use bin B",
)
```

The checkpoint contains the prior messages and pending tool calls, so approved
actions are continued without regenerating the original tool call. Configure
`JsonFileRuntimeState` if checkpoints must survive an agent restart.

## Persistent goals

Goals wrap tasks with durable state and a resume endpoint:

```python
from edgefleet import TaskRequest

goal = await client.create_goal(
    "Complete the component inspection",
    TaskRequest(
        input="Inspect part A-17",
        skill="inspect_part",
        reasoning=ReasoningConfig(
            mode=ReasoningMode.PLAN_EXECUTE,
            human_approval=True,
        ),
    ),
)

if goal.state == "waiting_approval":
    goal = await client.resume_goal(
        goal.id,
        approved_actions={"move_camera"},
    )
```

Run the orchestrator with persistent state:

```bash
edgefleet orchestrator \
  --state-file /var/lib/edgefleet/orchestrator.json
```

The JSON stores agents, task results, and goals. It is a single-process store;
use a transactional database implementation for multiple orchestrator
replicas.

## Automatic delegation

With `auto_delegate=True`, the LLM receives a `delegate_task` tool. Delegation
is routed through the orchestrator and includes cycle detection, visited-agent
tracking, and a configurable depth limit:

```python
ReasoningConfig(
    auto_delegate=True,
    max_delegation_depth=2,
)
```

Delegated child tasks disable further automatic delegation by default.

Equivalent HTTP request:

```bash
curl http://127.0.0.1:8000/v1/tasks \
  -H 'Authorization: Bearer development-secret' \
  -H 'Content-Type: application/json' \
  -d '{"input":{"message":"hello"},"skill":"echo"}'
```

## Define an edge agent

```python
from edgefleet import EdgeAgent, OpenAICompatibleLLM

agent = EdgeAgent(
    agent_id="vision-edge-1",
    name="Vision edge device",
    endpoint="http://vision-edge-1.local:8100",
    llm=OpenAICompatibleLLM(
        model="qwen3:4b",
        base_url="http://127.0.0.1:8080/v1",
    ),
    orchestrator_url="http://orchestrator.local:8000",
)

@agent.skill("inspect_part", description="Inspect a component")
async def inspect_part(task):
    return {"part": task.input["part"], "status": "ok"}
```

If no explicit skill handler matches, the local LLM handles the task.

## Actions and approvals

Actions are denied unless the submitted task sets `allow_actions=true`.
Controlled and dangerous actions pause and request approval unless their exact
action name is already present in `approved_actions`.

```python
from edgefleet import ActionPolicy, ActionRegistry

actions = ActionRegistry()

@actions.action(
    "set_gripper",
    description="Set gripper opening in millimeters",
    input_schema={
        "type": "object",
        "properties": {"opening_mm": {"type": "number"}},
        "required": ["opening_mm"],
    },
    policy=ActionPolicy.DANGEROUS,
)
async def set_gripper(opening_mm: float):
    return {"accepted": True, "opening_mm": opening_mm}
```

The caller must submit:

```python
await client.submit(
    "Open the gripper to 20 mm",
    allow_actions=True,
    approved_actions={"set_gripper"},
)
```

Approval is an application-level authorization boundary, not a substitute for
hardware interlocks, velocity/force limits, watchdogs, collision checking, or
an emergency stop.

## ROS 2 robot action

```python
from control_msgs.action import GripperCommand
from edgefleet.integrations.ros2 import ROS2ActionAdapter

def make_goal(arguments):
    goal = GripperCommand.Goal()
    goal.command.position = arguments["position"]
    goal.command.max_effort = arguments["max_effort"]
    return goal

robot_action = ROS2ActionAdapter(
    node_name="edgefleet_gripper",
    action_name="/gripper_controller/gripper_cmd",
    action_type=GripperCommand,
    goal_factory=make_goal,
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
    },
)

agent.actions.register(robot_action)
```

Use MoveIt 2 for collision-aware planning and `ros2_control` for deterministic
controller execution. For Wi-Fi or routed robot networks, configure ROS 2 to
use an appropriate Zenoh RMW or router deployment independently of EdgeFleet.

## MCP tools

```python
from edgefleet.integrations.mcp import MCPToolProvider

provider = MCPToolProvider("http://127.0.0.1:9000/mcp")
await provider.load_into(agent.actions)
```

Imported tools default to the `controlled` policy.

## NATS

The NATS adapter supports request/reply when direct inbound HTTP access to an
edge device is inconvenient:

```python
from edgefleet.integrations.nats import NATSTaskTransport

transport = NATSTaskTransport(["nats://nats.local:4222"])
await transport.connect()
await transport.serve(agent.agent_id, agent.execute)
```

The current adapter is request/reply. Add a JetStream-backed dispatcher before
depending on offline delivery and replay.

## A2A compatibility

Every agent exposes EdgeFleet discovery at
`/.well-known/agent-card.json`. An official A2A Protocol 1.0 JSON-RPC facade
can be mounted on the same FastAPI application:

```python
from edgefleet.integrations.a2a import mount_a2a

app = agent.create_app()
mount_a2a(app, agent)
```

The A2A Agent Card is then available at
`/.well-known/a2a-agent-card.json`, and JSON-RPC messages are accepted at
`/a2a` with the required `A2A-Version: 1.0` header. A2A message metadata can
select `skill`, `allow_actions`, and
`approved_actions`. Apply authentication middleware to these routes before
exposing them outside a trusted network.

## Production gaps

Version `0.0.0` is a working foundation, not a complete production robotics
platform. Before deployment, add:

- A transactional database store for multi-replica deployments.
- Per-device identities, TLS or mTLS, token rotation, and authorization scopes.
- Heartbeats, leases, load metrics, retry policy, and circuit breakers.
- JetStream persistence if tasks must survive disconnection.
- OpenTelemetry traces and device health metrics.
- A policy-backed approval service and authenticated approver identities.
- Simulation, hardware-in-the-loop tests, and independent safety controllers.

## Test

```bash
pytest
```

## Documentation

The complete Sphinx documentation is in `docs/`:

```bash
pip install -e '.[docs]'
make -C docs html
```

Open `docs/_build/html/index.html` after the build.

The use-case cookbook contains 236 generated Python programs:

```text
docs/use_cases/
```

The source catalog and generic runner are under `examples/use_cases/`.
