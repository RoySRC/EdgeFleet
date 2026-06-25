from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UseCase:
    category: str
    title: str
    slug: str
    target_agent: str
    skill: str
    prompt: str
    context: dict[str, str]
    mode: str
    reflection: bool = False
    memory: bool = False
    retrieval: bool = False
    auto_delegate: bool = False
    human_approval: bool = False
    allow_actions: bool = False
    pattern: str = "task"
    note: str = ""


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value


_CATEGORY_DATA: dict[str, dict[str, object]] = {
    "Robotics": {
        "agent": "robot-supervisor",
        "mode": "plan_execute",
        "context": {"site": "robot-cell-a", "robot": "robot-7"},
        "prompt": (
            "Use current robot state and registered tools to support {title}. "
            "Return a collision-aware plan, checks, and explicit stop conditions."
        ),
        "reflection": True,
        "human_approval": True,
        "titles": [
            "Robot-arm task planning",
            "Pick-and-place coordination",
            "Gripper control through approved ROS 2 actions",
            "Assembly assistance",
            "Sorting and packaging",
            "Visual inspection",
            "Mobile robot mission planning",
            "Navigation goal selection",
            "Warehouse robot coordination",
            "Agricultural robots",
            "Cleaning robots",
            "Construction robots",
            "Laboratory automation",
            "Drone mission supervision",
            "Underwater or marine robotics",
            "Search-and-rescue robots",
            "Teleoperation assistance",
            "Robot troubleshooting",
            "Collision-aware task planning",
            "Human-approved physical actions",
            "Multi-robot task delegation",
            "Robot fleet diagnostics",
        ],
    },
    "Industrial automation": {
        "agent": "plant-edge",
        "mode": "plan_execute",
        "context": {"plant": "plant-1", "line": "line-a"},
        "prompt": (
            "Analyze plant telemetry and local procedures for {title}. Return "
            "evidence, likely causes, verification steps, and safe operator actions."
        ),
        "reflection": True,
        "memory": True,
        "retrieval": True,
        "titles": [
            "Machine-condition monitoring",
            "Predictive-maintenance assistance",
            "Alarm interpretation",
            "Fault diagnosis",
            "Root-cause analysis",
            "Production-line inspection",
            "Quality-control reasoning",
            "Defect classification",
            "Process deviation analysis",
            "Operator copilots",
            "Maintenance procedure guidance",
            "Equipment commissioning",
            "Shift handover summaries",
            "Local manual retrieval",
            "Spare-part identification",
            "Safety checklist enforcement",
            "Human-approved machine commands",
            "Coordinating multiple production cells",
        ],
    },
    "IoT and embedded devices": {
        "agent": "iot-gateway",
        "mode": "direct",
        "context": {"gateway": "gateway-4", "network": "site-lan"},
        "prompt": (
            "Use local device state to implement {title}. Prefer deterministic "
            "device APIs, report uncertainty, and avoid unsupported configuration changes."
        ),
        "memory": True,
        "titles": [
            "Natural-language device interfaces",
            "Sensor-query agents",
            "Local telemetry interpretation",
            "Edge anomaly detection",
            "Device configuration",
            "Gateway management",
            "Remote-site diagnostics",
            "Offline device assistants",
            "Firmware troubleshooting",
            "Battery and power monitoring",
            "Local event correlation",
            "Coordinating heterogeneous sensors",
            "Actuator control through guarded actions",
        ],
    },
    "Smart buildings and homes": {
        "agent": "building-edge",
        "mode": "plan_execute",
        "context": {"building": "building-a", "zone": "floor-2"},
        "prompt": (
            "Use occupancy, environmental, and equipment data for {title}. "
            "Balance comfort, energy, privacy, and explicit safety constraints."
        ),
        "memory": True,
        "titles": [
            "HVAC optimization",
            "Energy-management assistance",
            "Lighting automation",
            "Occupancy-aware control",
            "Building fault diagnosis",
            "Appliance coordination",
            "Access-control workflows",
            "Security-camera analysis",
            "Local smart-home assistants",
            "Privacy-preserving home automation",
            "Fire or environmental sensor interpretation",
            "Human-approved door, alarm, or equipment control",
        ],
    },
    "Agriculture and environmental monitoring": {
        "agent": "field-edge",
        "mode": "plan_execute",
        "context": {"farm": "north-field", "station": "edge-station-2"},
        "prompt": (
            "Combine local sensor observations and field procedures for {title}. "
            "Return measurements used, recommended actions, and environmental safeguards."
        ),
        "retrieval": True,
        "titles": [
            "Crop monitoring",
            "Irrigation planning",
            "Greenhouse control",
            "Soil-sensor interpretation",
            "Livestock monitoring",
            "Pest-detection workflows",
            "Farm-equipment diagnosis",
            "Weather-station coordination",
            "Water-quality monitoring",
            "Forestry monitoring",
            "Wildfire sensor analysis",
            "Pollution monitoring",
            "Remote conservation stations",
        ],
    },
    "Logistics and warehouses": {
        "agent": "warehouse-edge",
        "mode": "plan_execute",
        "context": {"warehouse": "wh-3", "zone": "packing"},
        "prompt": (
            "Coordinate inventory, equipment, and workflow data for {title}. "
            "Return assignments, exception handling, and human approval points."
        ),
        "memory": True,
        "auto_delegate": True,
        "titles": [
            "Inventory inspection",
            "Package sorting",
            "Shipment exception handling",
            "Loading-dock coordination",
            "Barcode and label troubleshooting",
            "Cold-chain monitoring",
            "Route and task assignment",
            "Autonomous cart coordination",
            "Local warehouse copilots",
            "Damage assessment",
            "Equipment maintenance",
            "Persistent fulfillment goals",
        ],
    },
    "Vehicles and transportation": {
        "agent": "transport-supervisor",
        "mode": "plan_execute",
        "context": {"fleet": "fleet-2", "depot": "depot-east"},
        "prompt": (
            "Provide supervisory decision support for {title}. Analyze diagnostics "
            "and schedules, but leave safety-critical vehicle control to validated controllers."
        ),
        "reflection": True,
        "retrieval": True,
        "note": (
            "EdgeFleet supervises deterministic vehicle controllers; it must not "
            "perform direct safety-critical driving control."
        ),
        "titles": [
            "In-vehicle local assistants",
            "Vehicle diagnostics",
            "Fleet-maintenance assistance",
            "Charging-station coordination",
            "Railway equipment monitoring",
            "Port and terminal automation",
            "Marine-system diagnostics",
            "Mining-vehicle support",
            "Traffic-sensor coordination",
            "Public-transport equipment monitoring",
        ],
    },
    "Healthcare and laboratories": {
        "agent": "lab-edge",
        "mode": "plan_execute",
        "context": {"facility": "lab-a", "room": "instrument-room"},
        "prompt": (
            "Support {title} using authorized local data and validated procedures. "
            "Clearly separate observations from recommendations and require human review."
        ),
        "reflection": True,
        "retrieval": True,
        "human_approval": True,
        "note": (
            "Clinical decisions and regulated device control require separately "
            "validated systems and qualified human oversight."
        ),
        "titles": [
            "Medical-device troubleshooting",
            "Bedside equipment monitoring",
            "Local clinical documentation assistance",
            "Laboratory instrument coordination",
            "Sample-handling automation",
            "Environmental monitoring",
            "Inventory and reagent tracking",
            "Research-protocol assistance",
            "Human-approved lab robot actions",
            "Privacy-preserving local inference",
            "Accessibility interfaces",
        ],
    },
    "Retail and hospitality": {
        "agent": "facility-edge",
        "mode": "direct",
        "context": {"site": "store-12", "zone": "sales-floor"},
        "prompt": (
            "Use local operational data for {title}. Return a concise response, "
            "escalation criteria, and any required staff action."
        ),
        "memory": True,
        "titles": [
            "Shelf inspection",
            "Inventory assistants",
            "Refrigeration monitoring",
            "Checkout-device troubleshooting",
            "Store-energy management",
            "Service-robot coordination",
            "Kitchen-equipment monitoring",
            "Hotel-room automation",
            "Local customer-information kiosks",
            "Facility-maintenance assistance",
        ],
    },
    "Edge IT and networking": {
        "agent": "site-ops-edge",
        "mode": "plan_execute",
        "context": {"site": "branch-4", "environment": "production"},
        "prompt": (
            "Use local logs, configuration, and runbooks for {title}. Return "
            "evidence, blast radius, remediation plan, and rollback conditions."
        ),
        "reflection": True,
        "retrieval": True,
        "human_approval": True,
        "titles": [
            "Site-local infrastructure assistants",
            "Network-appliance diagnosis",
            "Log and alert triage",
            "Offline incident-response support",
            "Local cybersecurity analysis",
            "Configuration validation",
            "Service-health monitoring",
            "Remote branch management",
            "Private document retrieval",
            "Coordinating agents across servers",
            "Human-approved remediation actions",
        ],
    },
    "Remote and disconnected operations": {
        "agent": "remote-site-edge",
        "mode": "plan_execute",
        "context": {"site": "remote-7", "connectivity": "intermittent"},
        "prompt": (
            "Plan local-first support for {title}. Assume intermittent connectivity, "
            "preserve checkpoints, and identify tasks requiring durable delivery."
        ),
        "memory": True,
        "retrieval": True,
        "note": (
            "Use a durable transport extension such as JetStream before relying "
            "on eventual offline task delivery."
        ),
        "titles": [
            "Offshore platforms",
            "Mines",
            "Ships",
            "Research stations",
            "Disaster-response sites",
            "Rural infrastructure",
            "Military field logistics",
            "Space or planetary robotics research",
            "Temporary construction sites",
            "Intermittently connected sensor networks",
        ],
    },
    "Privacy-sensitive applications": {
        "agent": "private-edge",
        "mode": "direct",
        "context": {"deployment": "on-premises", "data_policy": "local-only"},
        "prompt": (
            "Implement {title} with local inference and local data access. "
            "Describe data boundaries and reject unnecessary external transmission."
        ),
        "memory": True,
        "retrieval": True,
        "titles": [
            "On-premises enterprise assistants",
            "Local document search",
            "Confidential manufacturing analysis",
            "Personal home assistants",
            "Private research environments",
            "Air-gapped operations",
            "Data-sovereignty deployments",
            "Devices that cannot send sensor data to cloud models",
        ],
    },
    "Multi-agent systems": {
        "agent": "fleet-supervisor",
        "mode": "debate",
        "context": {"fleet": "edge-fleet", "workflow": "coordination"},
        "prompt": (
            "Coordinate multiple specialist agents for {title}. Bound delegation, "
            "record agent contributions, and return a single resolved result."
        ),
        "auto_delegate": True,
        "titles": [
            "Specialist-agent delegation",
            "Supervisor-worker architectures",
            "Agent-to-agent task routing",
            "Per-device autonomous agents",
            "Multi-agent debate",
            "Consensus building",
            "Independent safety review",
            "Distributed problem solving",
            "Sensor-fusion reasoning",
            "Hierarchical agent fleets",
            "Agent capability discovery",
            "Cross-device workflow execution",
            "Bounded recursive delegation",
        ],
    },
    "Reasoning and decision-support workflows": {
        "agent": "reasoning-edge",
        "mode": "plan_execute",
        "context": {"workflow": "decision-support"},
        "prompt": (
            "Demonstrate {title} on the supplied operational question. Return "
            "application-visible reasoning artifacts and a concise final decision."
        ),
        "reflection": True,
        "pattern": "reasoning",
        "titles": [
            "Direct tool-using assistants",
            "Plan-then-execute workflows",
            "Answer reflection and revision",
            "Multiple-candidate self-consistency",
            "Tree-based proposal exploration",
            "Graph-based dependency exploration",
            "Multi-agent debate",
            "Structured decision summaries",
            "Context-aware prompting",
            "Skill-specific prompt templates",
            "Human-in-the-loop decisions",
            "Long-running resumable goals",
        ],
    },
    "Knowledge and retrieval": {
        "agent": "knowledge-edge",
        "mode": "direct",
        "context": {"knowledge_base": "site-documents"},
        "prompt": (
            "Use authorized local sources for {title}. Cite document identifiers, "
            "distinguish retrieved facts from inference, and report missing evidence."
        ),
        "memory": True,
        "retrieval": True,
        "pattern": "retrieval",
        "titles": [
            "Device manual retrieval",
            "Maintenance knowledge bases",
            "Standard operating procedures",
            "Local technical documentation",
            "Site-specific troubleshooting records",
            "Previous conversation recall",
            "Equipment service history",
            "Safety-procedure retrieval",
            "Distributed knowledge across agents",
            "Offline RAG deployments",
        ],
    },
    "Human approval workflows": {
        "agent": "approval-edge",
        "mode": "plan_execute",
        "context": {"workflow": "approval-demo"},
        "prompt": (
            "Prepare {title}. Pause before consequential execution and present "
            "the exact action, arguments, risk, and decision required from the human."
        ),
        "human_approval": True,
        "allow_actions": True,
        "pattern": "approval",
        "titles": [
            "Approving robot movements",
            "Confirming actuator commands",
            "Selecting between ambiguous plans",
            "Supplying missing parameters",
            "Authorizing high-risk tools",
            "Reviewing maintenance actions",
            "Confirming delegation",
            "Escalating uncertain decisions",
            "Pausing and resuming long-running workflows",
            "Maintaining approval audit records",
        ],
    },
    "Protocol and middleware gateway": {
        "agent": "gateway-edge",
        "mode": "direct",
        "context": {"gateway": "edge-gateway"},
        "prompt": "Bridge the requested system for {title} with explicit trust boundaries.",
        "pattern": "gateway",
        "titles": [
            "Local LLM-to-ROS 2 bridge",
            "LLM-to-MCP tool bridge",
            "Native agent-to-A2A facade",
            "HTTP-to-edge-device gateway",
            "NATS-based agent messaging",
            "LangGraph-based routing",
            "OpenAI-compatible local-model abstraction",
            "Wrapping legacy systems as guarded actions",
            "Unifying different edge-model runtimes",
        ],
    },
    "Development and research": {
        "agent": "research-edge",
        "mode": "self_consistency",
        "context": {"experiment": "edgefleet-evaluation"},
        "prompt": (
            "Run a controlled experiment for {title}. Record configuration, "
            "inputs, outputs, latency, failure modes, and reproducibility details."
        ),
        "pattern": "research",
        "titles": [
            "Embodied-AI experimentation",
            "Multi-agent reasoning research",
            "Local-model comparison",
            "Tool-calling evaluation",
            "Agent-routing experiments",
            "Human-approval research",
            "Robot-language interaction",
            "Edge inference benchmarking",
            "Persistent-agent experiments",
            "Simulated robot fleets",
            "Hardware-in-the-loop testing",
            "Agent safety-policy prototyping",
        ],
    },
    "Product patterns": {
        "agent": "product-edge",
        "mode": "plan_execute",
        "context": {"product": "edgefleet-application"},
        "prompt": (
            "Use EdgeFleet as the foundation for {title}. Define agents, skills, "
            "tools, persistence, deployment boundaries, and a minimal API workflow."
        ),
        "pattern": "product",
        "titles": [
            "An edge-agent operating system",
            "A robot copilot",
            "A distributed local assistant",
            "An industrial maintenance platform",
            "A privacy-first smart-building controller",
            "A multi-robot supervisor",
            "An offline field-operations assistant",
            "An intelligent IoT gateway",
            "A local automation platform",
            "A human-approved physical-action API",
        ],
    },
    "Poor fits without additional systems": {
        "agent": "safety-supervisor",
        "mode": "direct",
        "context": {"policy": "supervisory-only"},
        "prompt": (
            "Demonstrate the safe supervisory boundary for {title}. Do not execute "
            "the prohibited function; query status and hand off to a validated system."
        ),
        "pattern": "boundary",
        "note": (
            "The example intentionally demonstrates supervision or rejection, "
            "not implementation of the unsafe capability."
        ),
        "titles": [
            "Hard real-time motor control",
            "Emergency-stop logic",
            "Safety PLC functions",
            "Raw flight stabilization",
            "Autonomous medical decisions",
            "Unvalidated life-critical actions",
            "High-frequency control loops",
            "Guaranteed exactly-once offline delivery",
            "Multi-replica persistence using the current JSON stores",
            "Public internet exposure using only shared bearer tokens",
        ],
    },
}


_ACTION_KEYWORDS = {
    "control",
    "coordination",
    "automation",
    "commands",
    "actions",
    "movement",
    "configuration",
    "management",
    "routing",
}


def _mode_for(title: str, default: str) -> str:
    lower = title.lower()
    if "self-consistency" in lower or "comparison" in lower:
        return "self_consistency"
    if "tree-based" in lower:
        return "tree_search"
    if "graph-based" in lower:
        return "graph_search"
    if "debate" in lower or "consensus" in lower:
        return "debate"
    if "direct tool" in lower:
        return "direct"
    return default


def _build_cases() -> list[UseCase]:
    cases: list[UseCase] = []
    for category, spec in _CATEGORY_DATA.items():
        for raw_title in spec["titles"]:
            title = str(raw_title)
            slug = _slug(f"{category}-{title}")
            lower_words = set(re.findall(r"[a-z]+", title.lower()))
            action_like = bool(lower_words & _ACTION_KEYWORDS)
            cases.append(
                UseCase(
                    category=category,
                    title=title,
                    slug=slug,
                    target_agent=str(spec["agent"]),
                    skill=slug.replace("-", "_"),
                    prompt=str(spec["prompt"]).format(
                        title=title.lower()
                    ),
                    context=dict(spec["context"]),
                    mode=_mode_for(title, str(spec["mode"])),
                    reflection=bool(spec.get("reflection", False)),
                    memory=bool(spec.get("memory", False)),
                    retrieval=bool(spec.get("retrieval", False)),
                    auto_delegate=bool(
                        spec.get("auto_delegate", False)
                    ),
                    human_approval=bool(
                        spec.get("human_approval", False)
                    ),
                    allow_actions=bool(
                        spec.get("allow_actions", False)
                        or (
                            action_like
                            and category
                            not in {
                                "Poor fits without additional systems",
                                "Vehicles and transportation",
                            }
                        )
                    ),
                    pattern=str(spec.get("pattern", "task")),
                    note=str(spec.get("note", "")),
                )
            )
    return cases


USE_CASES = _build_cases()
CATEGORIES = tuple(_CATEGORY_DATA)
USE_CASES_BY_SLUG = {case.slug: case for case in USE_CASES}
