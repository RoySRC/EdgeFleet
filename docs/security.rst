Security and safety
===================

Threat model
------------

An EdgeFleet deployment processes natural language, retrieved documents,
network messages, model output, and commands that may affect physical systems.
Assume each of these can be malformed or adversarial.

Authentication
--------------

The native APIs support bearer tokens:

* orchestrator token for applications and agent registration;
* edge token for orchestrator-to-agent requests.

Bearer tokens are a development baseline. Production deployments should use
TLS, token rotation, scoped credentials, and preferably per-device identities
or mutual TLS.

Authorization
-------------

Current tokens are shared secrets and do not implement fine-grained scopes.
Add policy for:

* which clients may target which agents;
* which skills and actions each identity may invoke;
* who may approve controlled or dangerous actions;
* which documents a task may retrieve;
* which agents may delegate to one another.

Prompt injection
----------------

Retrieved data and tool output can contain malicious instructions.

Mitigations:

* treat retrieved text as data, not authority;
* separate system policy from retrieved context;
* permit only registered tools;
* validate every tool argument;
* use deterministic allowlists for physical actions;
* do not let model text modify credentials or policy;
* sanitize and label untrusted sources.

Action safety
-------------

``allow_actions`` is required before any action executes. Controlled and
dangerous actions require explicit names in ``approved_actions``.

This software gate is not a physical safety mechanism. Robot deployments
must independently enforce:

* emergency stop;
* watchdog and heartbeat;
* position, velocity, acceleration, force, and torque limits;
* collision and workspace constraints;
* controller state validation;
* command expiry and replay prevention;
* fail-safe behavior on network or model loss.

Human approval
--------------

Approval requests include action name, arguments, policy, task ID, and prompt.
Before production, bind approvals to an authenticated approver, timestamp,
policy decision, and immutable audit record.

Delegation safety
-----------------

EdgeFleet limits delegation depth and tracks visited agents. Also enforce:

* total task count and time budget;
* target-agent allowlists;
* per-agent rate limits;
* prevention of privilege escalation through a more capable child agent;
* propagation of tenant and authorization context.

Data protection
---------------

Memory, checkpoints, goals, and traces may contain sensitive data. The JSON
stores are unencrypted. Protect them with filesystem permissions and encrypted
storage, or replace them with a security-reviewed database.

Network exposure
----------------

Place APIs behind TLS and a firewall. Do not expose Ollama, llama.cpp, ROS 2,
NATS, or agent endpoints directly to the public internet without appropriate
authentication and segmentation.

Failure policy
--------------

Prefer fail-closed behavior:

* unavailable approval service means no physical action;
* invalid schemas mean no tool call;
* unknown agents mean routing failure;
* stale commands mean rejection;
* lost controller communication means safe stop.

