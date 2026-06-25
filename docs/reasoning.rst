Reasoning strategies
====================

Reasoning is configured per task with
:class:`~edgefleet.models.ReasoningConfig`. A primary mode can be combined
with reflection, memory, retrieval, delegation, and human-input support.

.. code-block:: python

   from edgefleet import ReasoningConfig, ReasoningMode

   config = ReasoningConfig(
       mode=ReasoningMode.PLAN_EXECUTE,
       reflection=True,
       reasoning_summary=True,
       memory=True,
       retrieval=True,
       auto_delegate=True,
       human_approval=True,
   )

Direct
------

``direct`` performs the standard prompt/tool loop:

1. construct system and user messages;
2. call the LLM with available tools;
3. execute approved tool calls;
4. return observations to the model;
5. stop when the model emits a final response.

Plan and execute
----------------

``plan_execute`` first requests a structured plan with steps, success
criteria, and risks. The plan is recorded in the trace and injected into the
execution prompt. Tool observations may cause the model to adapt the plan.

Use this for multi-step operational tasks where an explicit plan helps with
inspection, audit, and recovery.

Self-consistency
----------------

``self_consistency`` requests multiple independent candidate solutions and a
judge selection before final execution.

.. code-block:: python

   ReasoningConfig(
       mode=ReasoningMode.SELF_CONSISTENCY,
       samples=4,
   )

This increases model calls and latency. It is useful for ambiguous diagnosis
or analysis, but not for simple actuator commands.

Tree search
-----------

``tree_search`` explores distinct branches at each depth, judges them, and
continues along the selected path.

.. code-block:: python

   ReasoningConfig(
       mode=ReasoningMode.TREE_SEARCH,
       branches=3,
       depth=2,
   )

The implementation is bounded beam-like selection rather than an unbounded
search. Branches and decisions are recorded in the task trace.

Graph search
------------

``graph_search`` asks the model to build a small directed proposal graph,
including reusable or converging ideas, and then synthesize the strongest
route.

This is useful where dependencies are not naturally linear. Graph quality
depends on the selected model's structured-output reliability.

Debate
------

``debate`` gathers positions and resolves them with a judge.

Without named agents, three local personas are used:

* pragmatic implementer;
* skeptical safety reviewer;
* systems architect.

With ``debate_agents``, rounds are delegated through the orchestrator:

.. code-block:: python

   ReasoningConfig(
       mode=ReasoningMode.DEBATE,
       debate_agents=["vision-edge", "safety-edge"],
       debate_rounds=2,
   )

Reflection
----------

``reflection=True`` performs a critique-and-revision pass after the normal
answer is generated. The trace stores the critique and the fact that a
revision occurred.

Reasoning summaries
-------------------

``reasoning_summary=True`` asks for a concise decision summary containing the
methods and evidence used. EdgeFleet does not collect or expose hidden
token-by-token chain-of-thought.

Tool loop
---------

All modes converge on the same guarded tool loop. Planning or search does not
grant additional action permissions. Tools still require:

* ``allow_actions=True``;
* valid JSON-schema arguments;
* explicit approval for controlled or dangerous policies.

Cost and latency
----------------

Approximate model-call count before tool execution:

.. list-table::
   :header-rows: 1

   * - Mode
     - Calls before execution
   * - direct
     - 0
   * - plan_execute
     - 1
   * - self_consistency
     - ``samples + 1``
   * - tree_search
     - ``depth * (branches + 1)``
   * - graph_search
     - 2
   * - debate
     - depends on rounds and participants

Reflection adds two calls; a decision summary adds one.

Choosing a strategy
-------------------

Use ``direct`` for ordinary conversation and tool use. Use
``plan_execute`` for operational workflows. Reserve self-consistency and
search for high-ambiguity analysis. Use debate when independent agents have
meaningfully different sensors, models, or responsibilities.

