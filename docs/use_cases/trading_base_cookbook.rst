Base trading operations cookbook
================================

This cookbook covers the base trading operations scenario: a local,
human-approved pre-market portfolio review that can prepare broker actions but
must pause before execution.

For the ticker-discovery and multi-agent debate extension, see
:doc:`trading_advanced_cookbook`.

Base scenario: human-approved pre-market review
-----------------------------------------------

A complex financial example for EdgeFleet is a local, human-approved trading
operations copilot for a small fund, proprietary desk, treasury team, or
research trading environment. The operator wants help before the market opens,
when overnight events, earnings releases, pre-market moves, portfolio exposure,
liquidity, risk limits, and compliance constraints all need to be reconciled
quickly.

The operator gives a high-level request:

.. code-block:: text

   Review the technology portfolio before market open.
   Flag names with material overnight risk.
   Suggest risk-reducing hedge or rebalance actions.
   Do not send orders without approval.

The useful work is not autonomous trading. The useful work is coordinating
private data sources, local models, deterministic risk checks, compliance
rules, and human approval into one auditable workflow. EdgeFleet is a good fit
because the system can run on-premises, keep sensitive positions and research
notes local, and separate "reasoning about what might be useful" from
"permission to place an order."

In this scenario, the LLM should be treated as a decision-support component. It
can summarize evidence, generate candidate actions, call tools, and explain
tradeoffs. It should not be treated as a licensed advisor, a deterministic risk
engine, a compliance system of record, or an autonomous trading authority.
Pricing, position accounting, limit checks, restricted-list checks, order
validation, broker connectivity, audit logging, and final approval should be
owned by deterministic systems and qualified humans.

The deployment can be split across several edge agents:

* A trading gateway runs the orchestrator. It registers agents, stores task
  results, and manages persistent goals such as "complete the pre-market tech
  portfolio review".
* A market-data agent reads approved market feeds, pre-market prices, spreads,
  volume, volatility, and corporate-action data.
* A portfolio agent reads current positions, cash, open orders, sector
  exposure, unrealized profit and loss, and account restrictions.
* A research/RAG agent searches local news caches, filings, earnings
  transcripts, internal analyst notes, and mandate documents.
* A risk and compliance agent runs deterministic rules: position limits,
  concentration, liquidity, leverage, drawdown, restricted lists, mandate
  constraints, and required approvals.
* A strategy agent uses a local LLM to synthesize the observations and propose
  candidate actions.
* An execution agent converts an approved order basket into a broker API call.
  Its order-submission action is dangerous and must pause for human approval.

Base scenario workflow
----------------------

The workflow should be explicit and auditable:

#. The operator creates a persistent goal: complete the pre-market technology
   portfolio review.
#. The orchestrator routes the task to the strategy or trading coordinator
   agent.
#. The coordinator delegates bounded subtasks to the market-data, portfolio,
   research, and risk/compliance agents.
#. Deterministic agents return structured facts: positions, exposures,
   pre-market moves, liquidity, recent filings, restricted names, and current
   limit usage.
#. The local LLM summarizes the evidence and proposes candidate actions, such
   as reduce an oversized position, hedge sector exposure, cancel stale open
   orders, or do nothing.
#. The risk/compliance agent validates any candidate order basket with
   deterministic rules.
#. If the basket passes checks, the execution agent prepares a structured
   ``submit_order_batch`` tool call.
#. The action layer validates every order against JSON Schema. Because order
   submission is dangerous, EdgeFleet pauses the task and returns a pending
   approval request.
#. The human operator reviews the rationale, source data, risk checks,
   compliance checks, and exact order parameters.
#. The operator approves or rejects.
#. The orchestrator resumes the paused task. If approved, the execution agent
   sends the order basket through the broker adapter and stores the result.
#. The orchestrator stores the final task result and updates the persistent
   goal state.

This design also handles interruption. If the operator needs more context, the
task can pause for human input. If a feed is unavailable, the goal remains
visible and resumable. If a proposed order violates a limit, the deterministic
risk/compliance agent can reject it before the broker adapter is even called.

Base scenario component mapping
-------------------------------

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Responsibility
     - Use in this example
   * - Orchestrator
     - Registers trading agents, routes by ``target_agent`` or ``skill``,
       stores task results, resumes human approvals, and manages the persistent
       pre-market review goal.
   * - Edge agent
     - Each edge service advertises capabilities such as ``market_snapshot``,
       ``portfolio_snapshot``, ``validate_order_batch``, and
       ``review_portfolio_before_open``. Agents run deterministic Python skills,
       invoke local LLMs where useful, and store memory/checkpoints.
   * - LLM backend
     - Converts the operator request and retrieved evidence into summaries,
       candidate actions, and structured tool calls using a local
       OpenAI-compatible endpoint such as Ollama, llama.cpp, or vLLM.
   * - Action layer
     - Validates order arguments against JSON Schema and marks broker order
       submission as dangerous, requiring explicit approval.
   * - Integration layer
     - Optional adapters connect internal tools through MCP, route tasks over
       NATS, expose agents through A2A, or use LangGraph for richer routing.

Base scenario reference implementation
--------------------------------------

These snippets show the application structure. They are intentionally small;
real deployments need production market-data adapters, broker adapters,
position stores, compliance systems, and audit logging.

Orchestrator
~~~~~~~~~~~~

Run the orchestrator on a trading gateway or local operations server:

.. code-block:: python

   # trading_orchestrator.py
   import os

   from edgefleet import JsonFileStore, Orchestrator


   orchestrator = Orchestrator(
       store=JsonFileStore("state/trading-orchestrator.json"),
       token=os.getenv("EDGEFLEET_TOKEN"),
       edge_token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
   )

   app = orchestrator.create_app()

Start it with:

.. code-block:: console

   $ uvicorn trading_orchestrator:app --host 0.0.0.0 --port 8000

Market-data agent
~~~~~~~~~~~~~~~~~

The market-data agent should be deterministic. It reads approved data feeds and
returns structured facts. The LLM should not invent prices, spreads, or volume.

.. code-block:: python

   # market_data_agent.py
   import os

   from edgefleet import EdgeAgent, JsonFileRuntimeState


   agent = EdgeAgent(
       agent_id="market-data-agent",
       name="Market data agent",
       endpoint="http://market-data.local:8201",
       description="Approved market data, corporate actions, and liquidity",
       state=JsonFileRuntimeState("state/market-data-agent.json"),
       token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
       orchestrator_url="http://trading-gateway.local:8000",
       orchestrator_token=os.getenv("EDGEFLEET_TOKEN"),
   )


   @agent.skill(
       "market_snapshot",
       description="Return current market data for symbols or a sector watchlist.",
       tags=["market-data", "deterministic"],
   )
   async def market_snapshot(task):
       symbols = task.input.get("symbols", ["NVDA", "MSFT", "AAPL"])

       # Replace with approved market-data feed calls.
       return {
           "as_of": "2026-06-25T13:15:00Z",
           "symbols": [
               {
                   "symbol": symbol,
                   "premarket_change_pct": {
                       "NVDA": -4.2,
                       "MSFT": 0.6,
                       "AAPL": -0.4,
                   }.get(symbol, 0.0),
                   "spread_bps": 8,
                   "average_daily_volume": 50_000_000,
                   "corporate_action": None,
               }
               for symbol in symbols
           ],
       }


   app = agent.create_app()

Portfolio agent
~~~~~~~~~~~~~~~

The portfolio agent reads internal systems of record. The strategy agent should
not infer positions from conversation history.

.. code-block:: python

   # portfolio_agent.py
   import os

   from edgefleet import EdgeAgent, JsonFileRuntimeState


   agent = EdgeAgent(
       agent_id="portfolio-agent",
       name="Portfolio agent",
       endpoint="http://portfolio.local:8202",
       description="Positions, cash, exposure, P&L, and open orders",
       state=JsonFileRuntimeState("state/portfolio-agent.json"),
       token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
       orchestrator_url="http://trading-gateway.local:8000",
       orchestrator_token=os.getenv("EDGEFLEET_TOKEN"),
   )


   @agent.skill(
       "portfolio_snapshot",
       description="Return current positions and exposure for an account.",
       tags=["portfolio", "deterministic"],
   )
   async def portfolio_snapshot(task):
       account = task.input["account"]

       # Replace with PMS/OMS/accounting-system reads.
       return {
           "account": account,
           "cash_usd": 2_500_000,
           "gross_exposure_usd": 18_200_000,
           "net_exposure_usd": 9_700_000,
           "positions": [
               {
                   "symbol": "NVDA",
                   "quantity": 10_000,
                   "market_value_usd": 1_420_000,
                   "sector": "technology",
               },
               {
                   "symbol": "MSFT",
                   "quantity": 5_000,
                   "market_value_usd": 2_300_000,
                   "sector": "technology",
               },
           ],
           "open_orders": [],
       }


   app = agent.create_app()

Risk and compliance agent
~~~~~~~~~~~~~~~~~~~~~~~~~

Risk and compliance checks should be deterministic and conservative. The LLM
can explain a violation, but it should not decide whether a restricted-list or
limit breach is acceptable.

.. code-block:: python

   # risk_compliance_agent.py
   import os

   from edgefleet import EdgeAgent, JsonFileRuntimeState


   RESTRICTED_SYMBOLS = {"ACME"}
   MAX_SINGLE_ORDER_NOTIONAL_USD = 1_000_000


   agent = EdgeAgent(
       agent_id="risk-compliance-agent",
       name="Risk and compliance agent",
       endpoint="http://risk.local:8203",
       description="Deterministic risk limits and compliance checks",
       state=JsonFileRuntimeState("state/risk-compliance-agent.json"),
       token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
       orchestrator_url="http://trading-gateway.local:8000",
       orchestrator_token=os.getenv("EDGEFLEET_TOKEN"),
   )


   @agent.skill(
       "validate_order_batch",
       description="Validate a proposed order basket before approval.",
       tags=["risk", "compliance", "deterministic"],
   )
   async def validate_order_batch(task):
       violations = []
       warnings = []

       for order in task.input["orders"]:
           symbol = order["symbol"]
           estimated_notional = (
               order["quantity"] * order.get("limit_price", 0)
           )

           if symbol in RESTRICTED_SYMBOLS:
               violations.append(
                   {
                       "symbol": symbol,
                       "rule": "restricted_list",
                       "message": "Symbol is restricted for this account.",
                   }
               )

           if estimated_notional > MAX_SINGLE_ORDER_NOTIONAL_USD:
               violations.append(
                   {
                       "symbol": symbol,
                       "rule": "single_order_notional_limit",
                       "message": "Order notional exceeds configured limit.",
                   }
               )

           if order["order_type"] == "market":
               warnings.append(
                   {
                       "symbol": symbol,
                       "rule": "market_order_review",
                       "message": "Market orders require additional review.",
                   }
               )

       return {
           "passed": not violations,
           "violations": violations,
           "warnings": warnings,
       }


   app = agent.create_app()

Trading coordinator and execution agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The trading coordinator owns the local LLM and the guarded broker action. The
prompt instructs the model to gather evidence, validate candidate orders, and
only then prepare a broker-submission tool call. The action itself remains
schema-validated and dangerous.

.. code-block:: python

   # trading_coordinator_agent.py
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
       "submit_order_batch",
       description="Submit an approved basket of orders to the broker.",
       input_schema={
           "type": "object",
           "properties": {
               "account": {"type": "string"},
               "orders": {
                   "type": "array",
                   "minItems": 1,
                   "items": {
                       "type": "object",
                       "properties": {
                           "symbol": {"type": "string"},
                           "side": {
                               "type": "string",
                               "enum": ["buy", "sell", "sell_short", "cover"],
                           },
                           "quantity": {"type": "integer", "minimum": 1},
                           "order_type": {
                               "type": "string",
                               "enum": ["limit", "market"],
                           },
                           "limit_price": {"type": "number", "exclusiveMinimum": 0},
                           "time_in_force": {
                               "type": "string",
                               "enum": ["day", "ioc", "gtc"],
                           },
                           "rationale": {"type": "string"},
                       },
                       "required": [
                           "symbol",
                           "side",
                           "quantity",
                           "order_type",
                           "time_in_force",
                           "rationale",
                       ],
                       "additionalProperties": False,
                   },
               },
               "risk_check_id": {"type": "string"},
               "operator_note": {"type": "string"},
           },
           "required": ["account", "orders", "risk_check_id"],
           "additionalProperties": False,
       },
       policy=ActionPolicy.DANGEROUS,
   )
   async def submit_order_batch(
       account: str,
       orders: list[dict],
       risk_check_id: str,
       operator_note: str | None = None,
   ):
       # Replace with broker or OMS API calls. A production implementation
       # should bind approval to the exact order payload and write an audit log
       # before sending anything externally.
       return {
           "account": account,
           "risk_check_id": risk_check_id,
           "broker_status": "submitted",
           "orders": [
               {
                   "symbol": order["symbol"],
                   "client_order_id": f"demo-{index}",
                   "status": "accepted",
               }
               for index, order in enumerate(orders, start=1)
           ],
           "operator_note": operator_note,
       }


   llm = OpenAICompatibleLLM(
       model=os.getenv("EDGEFLEET_MODEL", "qwen3:1.7b"),
       base_url=os.getenv("EDGEFLEET_LLM_URL", "http://127.0.0.1:11434/v1"),
       api_key=os.getenv("EDGEFLEET_LLM_API_KEY", "local"),
   )

   retriever = InMemoryRetriever(
       [
           Document(
               id="trading-policy",
               text=(
                   "The LLM may propose trades but may not submit orders "
                   "without human approval. Restricted-list and risk-limit "
                   "failures are hard stops. Prefer limit orders when spreads "
                   "are wide. Record the evidence used for each proposal."
               ),
           )
       ]
   )

   agent = EdgeAgent(
       agent_id="trading-coordinator-agent",
       name="Trading coordinator",
       endpoint="http://trading-coordinator.local:8204",
       description="Coordinates pre-market review and guarded execution",
       llm=llm,
       actions=actions,
       retriever=retriever,
       state=JsonFileRuntimeState("state/trading-coordinator-agent.json"),
       token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
       orchestrator_url="http://trading-gateway.local:8000",
       orchestrator_token=os.getenv("EDGEFLEET_TOKEN"),
   )

   agent.prompt_skill(
       "review_portfolio_before_open",
       description="Review a portfolio and prepare human-approved orders.",
       prompt_template=(
           "You are a trading operations copilot, not an autonomous trader.\n"
           "Task: {input}\n"
           "Context: {context}\n"
           "Policy: {retrieved_context}\n\n"
           "Required behavior:\n"
           "1. Delegate market data to market-data-agent with skill "
           "market_snapshot.\n"
           "2. Delegate positions to portfolio-agent with skill "
           "portfolio_snapshot.\n"
           "3. Propose candidate actions only if supported by the data.\n"
           "4. Delegate proposed orders to risk-compliance-agent with skill "
           "validate_order_batch.\n"
           "5. If checks fail, do not call submit_order_batch.\n"
           "6. If checks pass and orders are useful, call submit_order_batch "
           "with the exact validated order basket. EdgeFleet will pause for "
           "human approval before execution.\n"
           "7. If no action is warranted, summarize why."
       ),
   )


   app = agent.create_app()

Operator client
~~~~~~~~~~~~~~~

The operator client creates a persistent goal and resumes it only after the
human reviews the pending order action.

.. code-block:: python

   # run_premarket_review.py
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
           os.getenv("EDGEFLEET_URL", "http://trading-gateway.local:8000"),
           token=os.getenv("EDGEFLEET_TOKEN"),
           timeout=300,
       )

       task = TaskRequest(
           input={
               "account": "tech-long-short",
               "sector": "technology",
               "instruction": (
                   "Review the technology portfolio before market open. "
                   "Flag overnight risk. Suggest risk-reducing actions. "
                   "Do not send orders without approval."
               ),
           },
           skill="review_portfolio_before_open",
           target_agent="trading-coordinator-agent",
           allow_actions=True,
           conversation_id="trading/pre-market/tech",
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

       goal = await client.create_goal(
           "Complete pre-market technology portfolio review",
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

               answer = input("Approve this exact broker action? [yes/no] ")
               if answer.lower() != "yes":
                   raise SystemExit("Operator rejected order submission.")

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
               response = input(f"{result.pending_question} ")
               goal = await client.resume_goal(
                   goal.id,
                   human_input=response,
               )
               print(goal.model_dump_json(indent=2))
               continue

           break


   if __name__ == "__main__":
       asyncio.run(main())

Optional integration hooks
--------------------------
Broker, data, and research systems are usually application-specific. EdgeFleet
keeps these integrations optional.

MCP tools for internal systems
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If an internal research, data, or broker gateway already exposes MCP tools,
import those tools into an action registry. Choose the policy carefully:
read-only tools can be safe, while order-entry tools should be dangerous.

.. code-block:: python

   from edgefleet import ActionPolicy
   from edgefleet.integrations.mcp import MCPToolProvider


   await MCPToolProvider(
       "http://research-gateway.local:9000/mcp",
       policy=ActionPolicy.SAFE,
   ).load_into(actions)

NATS transport
~~~~~~~~~~~~~~

Use NATS when agents live on separate subnets or where direct HTTP service
discovery is awkward.

.. code-block:: python

   from edgefleet.integrations.nats import NATSTaskTransport


   transport = NATSTaskTransport(["nats://trading-gateway.local:4222"])
   await transport.connect()
   await transport.serve("market-data-agent", agent.execute)

A2A facade
~~~~~~~~~~

Expose the trading coordinator to other A2A-compatible agents without changing
the EdgeFleet agent implementation.

.. code-block:: python

   from edgefleet.integrations.a2a import mount_a2a


   app = agent.create_app()
   mount_a2a(app, agent)

LangGraph routing
~~~~~~~~~~~~~~~~~

Use LangGraph when routing depends on asset class, market session, region, or
account type instead of simple skill matching.

.. code-block:: python

   from edgefleet import Orchestrator
   from edgefleet.routing import LangGraphRouter


   orchestrator = Orchestrator(
       router=LangGraphRouter(compiled_graph),
       token=os.getenv("EDGEFLEET_TOKEN"),
       edge_token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
   )
