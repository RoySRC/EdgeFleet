Advanced trading debate cookbook
================================

This cookbook covers the advanced trading operations scenario: ticker
discovery, bull/bear debate, deterministic risk and compliance blockers, and
approval-gated execution.

The advanced scenario extends the base pre-market review pattern, so this page
includes both the shared base infrastructure and the advanced agents required
to run the full workflow.

Advanced scenario: ticker discovery and multi-agent debate
----------------------------------------------------------

A more advanced deployment adds a ticker-suggestion agent and a structured
debate stage. This is useful when the operator does not only want a review of
current holdings, but also wants to know which adjacent names, peers, ETFs, or
hedge candidates deserve attention before the open.

The operator might ask:

.. code-block:: text

   Review the technology book before market open.
   Include current holdings, related semiconductor names, and relevant hedge
   candidates. Debate the bull and bear cases before proposing any action.
   Risk and compliance must be able to block the recommendation.
   Do not send orders without approval.

The advanced system expands the review universe, gathers evidence, and then
runs a bounded agentic loop. In each round, bull and bear agents argue from the
same evidence, critique the opposing view, and the strategy agent revises or
stabilizes the candidate recommendation. Risk and compliance checks run after
each candidate revision. If either blocks the candidate, the loop must revise
within the remaining round budget or stop without execution.

The ticker-suggestion agent expands what the system looks at; it does not
expand what the system is allowed to trade.

Component responsibilities
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 22 45 33

   * - Component
     - What it does
     - What it must not do
   * - Orchestrator
     - Owns the persistent pre-market review goal, registers every agent,
       routes subtasks, stores all debate outputs, and resumes approval pauses.
     - It does not make investment judgments or bypass agent-level controls.
   * - Strategy agent
     - Coordinates the workflow, asks for ticker suggestions, builds the
       evidence package, requests bull/bear/risk/compliance reviews, and
       produces the final recommendation with disagreement noted.
     - It does not submit orders directly or override risk/compliance blocks.
   * - Ticker-suggestion agent
     - Suggests additional tickers to review from holdings, watchlists,
       pre-market movers, peers, ETFs, supply-chain names, research notes, and
       sector mappings.
     - It does not recommend side, quantity, price, or execution. Every output
       is ``review_only``.
   * - Portfolio agent
     - Returns current positions, open orders, cash, exposure, account mandate,
       and watchlist names from internal systems of record.
     - It does not infer positions from model context or conversation memory.
   * - Market-data agent
     - Returns current or latest-approved prices, pre-market changes, spreads,
       volume, corporate actions, and data freshness.
     - It does not invent missing prices or silently ignore stale data.
   * - Research/RAG agent
     - Retrieves local news, filings, transcripts, internal notes, policy
       documents, and prior decision records relevant to the review scope.
     - It does not treat retrieved commentary as permission to trade.
   * - Bull case agent
     - Argues for holding, adding, or minimizing action. It identifies upside
       catalysts, positive evidence, and reasons the current risk may be
       acceptable.
     - It does not approve execution or ignore hard risk/compliance limits.
   * - Bear case agent
     - Argues for reducing, hedging, or exiting. It identifies downside risks,
       adverse news, concentration, liquidity, and event risk.
     - It does not approve execution or fabricate negative evidence.
   * - Risk agent
     - Runs deterministic portfolio and order checks: concentration, leverage,
       liquidity, notional limits, factor exposure, drawdown, and max order
       size.
     - It does not weigh investment merit. It can block but should not decide
       the trade thesis.
   * - Compliance agent
     - Runs deterministic mandate, restricted-list, account-permission,
       approval, and audit-policy checks.
     - It does not weigh investment merit. It can block anything outside the
       mandate or approval policy.
   * - Execution agent
     - Converts an approved order basket into a broker or OMS request after
       EdgeFleet approval has resumed the paused task.
     - It does not invent orders, change payloads after approval, or execute
       rejected actions.
   * - Action layer
     - Validates order payloads against JSON Schema and marks order submission
       as dangerous.
     - It does not decide whether a trade is economically attractive.
   * - Human operator
     - Reviews the final recommendation, dissenting views, checks, and exact
       broker payload before approving or rejecting execution.
     - They should not be asked to approve vague actions. The payload must be
       explicit.

Detailed agent roles
~~~~~~~~~~~~~~~~~~~~

The advanced workflow works because each agent has a narrow responsibility.
The agents can share evidence, but they should not share authority. Ticker
discovery expands the review universe, debate agents argue constrained cases
across bounded rounds, risk and compliance agents block invalid actions after
each candidate revision, and the execution agent only acts after approval.

Strategy coordinator agent
^^^^^^^^^^^^^^^^^^^^^^^^^^

The strategy coordinator is the workflow owner for the advanced review. It
receives the operator's high-level request, creates the review plan, delegates
bounded subtasks, and assembles the final recommendation. It should be the
only agent responsible for reconciling conflicting views into one operator
summary.

Its inputs are the operator request, account context, portfolio snapshot,
candidate ticker universe, market data, retrieved research, the current round's
bull case, bear case, cross-critiques, risk review, and compliance review. Its
output should include the review scope, the evidence used, round-by-round
disagreements, any blocked actions, and the final recommendation.

The strategy coordinator can recommend actions, but it cannot override a hard
risk or compliance block. It also cannot execute orders directly. If execution
is warranted, it must call the guarded order action with an exact payload and
let EdgeFleet pause for human approval.

The strategy coordinator also owns the debate stopping conditions. It should
stop when the recommendation is stable, risk or compliance blocks further
progress, confidence remains too low and human input is needed, the maximum
round count is reached, or an approval-ready payload has been produced.

Ticker-suggestion agent
^^^^^^^^^^^^^^^^^^^^^^^

The ticker-suggestion agent expands the set of names that deserve review. It
is useful when the operator starts with a broad instruction such as "review the
technology book" or when overnight news affects related names that are not
current holdings.

Its inputs are current holdings, watchlists, sector or factor maps, peer lists,
supplier/customer relationships, ETF constituents, pre-market movers, local
research notes, and restricted or out-of-mandate lists. Its output should be a
bounded JSON list of suggested tickers with a reason, relationship type,
priority, and ``allowed_use`` set to ``review_only``.

The ticker-suggestion agent must not propose order side, quantity, price,
order type, or execution timing. It does not decide what can be traded. It only
decides what should be examined.

Portfolio agent
^^^^^^^^^^^^^^^

The portfolio agent is the source of truth for the current book. It should read
positions, cash, open orders, account permissions, exposure, unrealized profit
and loss, and mandate information from internal systems of record.

Its output should be structured and timestamped. For the advanced workflow, it
should also include the account watchlist, sector tags, position sizes, and any
known account-level restrictions that affect review-scope construction.

The portfolio agent must not infer positions from prompts, conversation
history, or model-generated summaries. If the system of record is unavailable,
it should fail or mark the data stale rather than provide an estimate.

Market-data agent
^^^^^^^^^^^^^^^^^

The market-data agent provides observable market facts for the review scope.
It should return prices, pre-market moves, bid/ask spreads, volume, average
daily volume, corporate actions, volatility, liquidity flags, and data
freshness metadata.

Its output is consumed by the strategy, bull, bear, and risk agents. The risk
agent may use the same data for notional, liquidity, and concentration checks,
so freshness and source metadata matter.

The market-data agent must not invent missing prices or silently substitute an
LLM estimate. If a feed is stale, delayed, or partial, the output should say
so explicitly. A stale feed should normally block execution.

Research/RAG agent
^^^^^^^^^^^^^^^^^^

The research/RAG agent retrieves qualitative context from local sources:
filings, earnings transcripts, news, analyst notes, prior decision records,
mandate documents, and internal policy. Its job is to ground the discussion in
retrieved evidence without exposing private documents outside the local
deployment.

Its output should cite document IDs, timestamps, source categories, and short
summaries. The strategy, bull, and bear agents can use those summaries to
construct arguments, while compliance can use policy retrieval to enforce
mandate or approval rules.

The research/RAG agent must not treat retrieved commentary as permission to
trade. A bullish analyst note is evidence, not authorization. A policy
document may define constraints, but deterministic compliance checks should
still enforce them.

Bull case agent
^^^^^^^^^^^^^^^

The bull case agent argues for holding, adding, or minimizing action. It
should identify constructive evidence such as positive catalysts, strong
liquidity, limited risk impact, favorable earnings interpretation, or reasons
an overnight move may be temporary.

Its first-round input is the same evidence package used by the bear case
agent. In later rounds, it also receives the bear case and the strategy
agent's current candidate recommendation. Its output should include a
recommendation, confidence, supporting evidence, key uncertainties, a critique
of the bear case, and the strongest evidence that could invalidate the bullish
case.

The bull case agent must not ignore hard risk or compliance constraints. It is
allowed to persuade the strategy agent, but it is not allowed to approve
execution or convert its argument into an order.

Bear case agent
^^^^^^^^^^^^^^^

The bear case agent argues for reducing, hedging, exiting, or taking no
additional exposure. It should identify adverse news, event risk,
concentration, liquidity deterioration, elevated volatility, downside
scenarios, and weak points in the bull case.

Its first-round input is the same evidence package used by the bull case
agent. In later rounds, it also receives the bull case and the strategy
agent's current candidate recommendation. Its output should mirror the bull
case structure: recommendation, confidence, evidence, uncertainties, critique
of the bull case, and the strongest evidence that could invalidate the bearish
case. Keeping the output schema aligned makes the final debate record easier
to compare and audit.

The bear case agent must not fabricate negative evidence or overstate
constraints. Like the bull case agent, it can persuade but cannot approve or
execute.

Risk agent
^^^^^^^^^^

The risk agent runs deterministic checks on proposed actions. It evaluates
concentration, leverage, liquidity, order notional, factor exposure, drawdown,
max position size, and account-specific risk limits. It should produce
machine-readable pass/fail results and explain each violation.

Its inputs are the portfolio snapshot, market data, proposed order basket, and
configured risk limits. Its output should distinguish hard violations from
warnings. For example, "buying more is blocked by concentration" is different
from "selling 1,000 shares passes but liquidity is thin."

The risk agent runs after every strategy candidate that implies an order. It
does not decide whether the investment thesis is attractive. It can block
invalid actions, restrict order size, or require additional review, but it
should not invent a trade.

Compliance agent
^^^^^^^^^^^^^^^^

The compliance agent runs deterministic mandate and policy checks. It verifies
restricted lists, account permissions, instrument eligibility, short-sale
rules, approval requirements, audit requirements, and mandate constraints.

Its inputs are the account context, proposed order basket, restricted symbols,
policy configuration, and any retrieved compliance documents. Its output
should identify hard blocks, required approvals, policy references, and audit
metadata that must accompany execution.

The compliance agent runs after every strategy candidate that implies an
order. It should be able to veto a recommendation even if the bull, bear, and
strategy agents agree. It does not judge investment merit; it judges whether
the proposed action is allowed.

Execution agent
^^^^^^^^^^^^^^^

The execution agent owns the broker or OMS adapter. It receives an exact order
payload only after strategy, risk, and compliance have produced a candidate
that is ready for approval. Its EdgeFleet action should be marked dangerous so
the task pauses before the broker call.

Its inputs are the validated order basket, account, risk-check ID, compliance
metadata, and human approval. Its output should include broker status, client
order IDs, accepted/rejected order details, timestamps, and any execution
errors returned by the broker or OMS.

The execution agent must not change the approved order payload after approval.
If market conditions changed, the broker adapter should reject or pause rather
than mutate the order. Production deployments should bind approval to the
exact order payload and audit ID.

Loop-based advanced workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The advanced flow is a bounded loop, not a single-pass debate:

.. code-block:: text

   Human operator
     -> Orchestrator persistent goal
       -> Strategy agent
         -> Portfolio agent: current holdings, watchlist, account constraints
         -> Ticker-suggestion agent: additional review-only names
         -> Market-data agent: prices, pre-market moves, liquidity, freshness
         -> Research/RAG agent: filings, news, notes, policy context
         -> Evidence package
         -> Debate loop, maximum N rounds
           -> Bull case agent: argue or revise constructive case
           -> Bear case agent: argue or revise risk-reduction case
           -> Bull case agent: critique bear case
           -> Bear case agent: critique bull case
           -> Strategy agent: revise candidate recommendation
           -> Risk agent: validate candidate order basket
           -> Compliance agent: validate candidate order basket
           -> Stop, revise, or continue to next round
         -> Structured loop record with round history
         -> Final recommendation or no-action report
         -> Dangerous broker action pauses for approval
           -> Human approval or rejection
             -> Execution agent
               -> Broker/OMS adapter
                 -> Stored result and audit trail

Each round has the same basic contract:

.. code-block:: text

   round_input =
       evidence package
       + prior round record, if any
       + current candidate recommendation, if any

   round_output =
       bull argument
       + bear argument
       + cross-critiques
       + revised candidate
       + risk validation
       + compliance validation
       + continue/stop decision

Stop the loop when one of these conditions is met:

* risk blocks the candidate and no safe revision is available;
* compliance blocks the candidate and no allowed revision is available;
* the recommendation does not materially change after a round;
* the confidence remains too low and human input is required;
* the maximum debate round count is reached;
* the final candidate is ready for human approval; or
* the best action is to do nothing and explain why.

The authority boundaries are intentionally asymmetric:

.. code-block:: text

   Ticker agent can expand the review universe.
   Bull and bear agents can persuade across bounded rounds.
   Strategy agent can revise and recommend.
   Risk and compliance agents can block each revised candidate.
   Execution agent can prepare or send only approved orders.
   Human operator approves.
   Broker/OMS adapter executes.

Ticker-suggestion output
~~~~~~~~~~~~~~~~~~~~~~~~

The ticker-suggestion agent should return bounded structured output. It should
not return trade instructions.

.. code-block:: json

   {
     "base_scope": ["NVDA", "MSFT", "AAPL"],
     "suggested_tickers": [
       {
         "symbol": "AMD",
         "reason": "Peer exposed to the same overnight semiconductor news.",
         "relationship": "peer",
         "priority": "high",
         "allowed_use": "review_only"
       },
       {
         "symbol": "SMH",
         "reason": "Semiconductor ETF useful for sector hedge analysis.",
         "relationship": "hedge_candidate",
         "priority": "medium",
         "allowed_use": "review_only"
       },
       {
         "symbol": "TSM",
         "reason": "Supply-chain exposure relevant to semiconductor holdings.",
         "relationship": "supplier_or_related_exposure",
         "priority": "medium",
         "allowed_use": "review_only"
       }
     ],
     "excluded": [
       {
         "symbol": "ACME",
         "reason": "Restricted list"
       }
     ]
   }

The strategy agent merges the scope conservatively:

.. code-block:: text

   review_scope =
       current holdings
       + approved watchlist names
       + ticker-suggestion candidates
       - restricted symbols
       - names outside mandate

Structured loop record
~~~~~~~~~~~~~~~~~~~~~~

The debate loop should be stored as data, not only as chat text. That makes
the result easier to audit and easier for the final strategy agent to consume.

.. code-block:: json

   {
     "symbol": "NVDA",
     "review_scope_reason": "Current holding and high-priority overnight mover.",
     "max_rounds": 3,
     "rounds": [
       {
         "round": 1,
         "bull_case": {
           "recommendation": "hold",
           "confidence": 0.62,
           "evidence": [
             "High liquidity",
             "No hard compliance block",
             "Pre-market move may be temporary"
           ],
           "bear_case_critique": "Concentration concern is valid but sell size may be too aggressive."
         },
         "bear_case": {
           "recommendation": "reduce",
           "confidence": 0.74,
           "evidence": [
             "Material overnight negative news",
             "Single-name exposure is elevated",
             "Pre-market drawdown increases opening risk"
           ],
           "bull_case_critique": "Liquidity does not remove event risk at the open."
         },
         "candidate_recommendation": {
           "action": "sell",
           "quantity": 1500,
           "order_type": "limit"
         },
         "risk_review": {
           "passed": true,
           "blocked_actions": ["increase_position"],
           "allowed_actions": ["sell_up_to_1500_shares"]
         },
         "compliance_review": {
           "passed": true,
           "constraints": [
             "limit_order_preferred",
             "human_approval_required"
           ]
         },
         "decision": "continue",
         "reason": "Reduce size one more round because bull critique flagged oversizing risk."
       },
       {
         "round": 2,
         "candidate_recommendation": {
           "action": "sell",
           "quantity": 1000,
           "order_type": "limit"
         },
         "risk_review": {
           "passed": true,
           "allowed_actions": ["sell_up_to_1500_shares"]
         },
         "compliance_review": {
           "passed": true,
           "constraints": [
             "limit_order_preferred",
             "human_approval_required"
           ]
         },
         "decision": "stop",
         "reason": "Recommendation stabilized and passes checks."
       }
     ],
     "final_recommendation": {
       "action": "sell",
       "quantity": 1000,
       "order_type": "limit",
       "requires_approval": true
     }
   }

Shared base implementation
--------------------------

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

Example advanced agents
~~~~~~~~~~~~~~~~~~~~~~~

The ticker-suggestion agent can be implemented as a prompt-backed local-LLM
agent because its job is reasoning over provided evidence. Its prompt should
make the authority boundary explicit.

.. code-block:: python

   # ticker_suggestion_agent.py
   import os

   from edgefleet import EdgeAgent, JsonFileRuntimeState, OpenAICompatibleLLM


   agent = EdgeAgent(
       agent_id="ticker-suggestion-agent",
       name="Ticker suggestion agent",
       endpoint="http://ticker-suggestion.local:8205",
       description="Suggests review-only tickers related to a portfolio scope",
       llm=OpenAICompatibleLLM(
           model=os.getenv("EDGEFLEET_MODEL", "qwen3:1.7b"),
           base_url=os.getenv("EDGEFLEET_LLM_URL", "http://127.0.0.1:11434/v1"),
           api_key=os.getenv("EDGEFLEET_LLM_API_KEY", "local"),
       ),
       state=JsonFileRuntimeState("state/ticker-suggestion-agent.json"),
       token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
       orchestrator_url="http://trading-gateway.local:8000",
       orchestrator_token=os.getenv("EDGEFLEET_TOKEN"),
   )

   agent.prompt_skill(
       "suggest_tickers",
       description="Suggest additional review-only tickers for a portfolio review.",
       prompt_template=(
           "You suggest tickers for review, not trades.\n"
           "Use only the provided holdings, watchlists, market data, research "
           "notes, and policy context.\n"
           "Return JSON with base_scope, suggested_tickers, and excluded.\n"
           "Each suggested ticker must include symbol, reason, relationship, "
           "priority, and allowed_use='review_only'.\n"
           "Do not recommend side, quantity, price, order type, or execution.\n"
           "Exclude restricted or out-of-mandate symbols if provided.\n\n"
           "Task: {input}\n"
           "Context: {context}"
       ),
   )


   app = agent.create_app()

Bull and bear agents can also be prompt-backed agents. They receive the same
evidence package but are assigned different argumentative roles.

.. code-block:: python

   # bull_case_agent.py
   import os

   from edgefleet import EdgeAgent, JsonFileRuntimeState, OpenAICompatibleLLM


   agent = EdgeAgent(
       agent_id="bull-case-agent",
       name="Bull case agent",
       endpoint="http://bull-case.local:8206",
       description="Argues the constructive case for reviewed symbols",
       llm=OpenAICompatibleLLM(
           model=os.getenv("EDGEFLEET_MODEL", "qwen3:1.7b"),
           base_url=os.getenv("EDGEFLEET_LLM_URL", "http://127.0.0.1:11434/v1"),
           api_key=os.getenv("EDGEFLEET_LLM_API_KEY", "local"),
       ),
       state=JsonFileRuntimeState("state/bull-case-agent.json"),
       token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
       orchestrator_url="http://trading-gateway.local:8000",
       orchestrator_token=os.getenv("EDGEFLEET_TOKEN"),
   )

   agent.prompt_skill(
       "argue_bull_case",
       description="Argue for holding, adding, or minimizing action.",
       prompt_template=(
           "You are the bull-case reviewer. Argue only from the supplied "
           "evidence.\n"
           "Inputs may include an evidence package, prior round record, "
           "current candidate recommendation, and bear-case argument.\n"
           "Return JSON with recommendation, confidence, evidence, "
           "key_uncertainties, bear_case_critique, and invalidating_evidence.\n"
           "Do not approve execution.\n\n"
           "Round input: {input}"
       ),
   )


   app = agent.create_app()

.. code-block:: python

   # bear_case_agent.py
   import os

   from edgefleet import EdgeAgent, JsonFileRuntimeState, OpenAICompatibleLLM


   agent = EdgeAgent(
       agent_id="bear-case-agent",
       name="Bear case agent",
       endpoint="http://bear-case.local:8207",
       description="Argues the risk-reduction case for reviewed symbols",
       llm=OpenAICompatibleLLM(
           model=os.getenv("EDGEFLEET_MODEL", "qwen3:1.7b"),
           base_url=os.getenv("EDGEFLEET_LLM_URL", "http://127.0.0.1:11434/v1"),
           api_key=os.getenv("EDGEFLEET_LLM_API_KEY", "local"),
       ),
       state=JsonFileRuntimeState("state/bear-case-agent.json"),
       token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
       orchestrator_url="http://trading-gateway.local:8000",
       orchestrator_token=os.getenv("EDGEFLEET_TOKEN"),
   )

   agent.prompt_skill(
       "argue_bear_case",
       description="Argue for reducing, hedging, or exiting.",
       prompt_template=(
           "You are the bear-case reviewer. Argue only from the supplied "
           "evidence.\n"
           "Inputs may include an evidence package, prior round record, "
           "current candidate recommendation, and bull-case argument.\n"
           "Return JSON with recommendation, confidence, evidence, "
           "key_uncertainties, bull_case_critique, and invalidating_evidence.\n"
           "Do not approve execution.\n\n"
           "Round input: {input}"
       ),
   )


   app = agent.create_app()

The strategy coordinator prompt can then explicitly invoke those agents:

.. code-block:: python

   agent.prompt_skill(
       "advanced_portfolio_debate",
       description=(
           "Run ticker discovery, bounded debate rounds, checks, and "
           "approval-gated execution."
       ),
       prompt_template=(
           "You coordinate a pre-market trading review. You are not an "
           "autonomous trader.\n"
           "Task: {input}\n"
           "Context: {context}\n"
           "Policy: {retrieved_context}\n\n"
           "Required behavior:\n"
           "1. Ask portfolio-agent for portfolio_snapshot.\n"
           "2. Ask ticker-suggestion-agent for suggest_tickers.\n"
           "3. Build the review scope from holdings, watchlist names, and "
           "review-only suggestions, excluding restricted or out-of-mandate "
           "symbols.\n"
           "4. Ask market-data-agent for market_snapshot on the review scope.\n"
           "5. Ask the research/RAG source for relevant filings, notes, and "
           "policy context.\n"
           "6. Run a bounded debate loop. Use context.max_debate_rounds if "
           "provided; otherwise use at most 3 rounds.\n"
           "7. In each round, send the evidence package, prior round record, "
           "and current candidate to bull-case-agent and bear-case-agent.\n"
           "8. Ask each side to critique the other side, then revise the "
           "candidate recommendation.\n"
           "9. Ask risk-compliance-agent to validate every candidate order "
           "basket after each revision.\n"
           "10. Stop the loop if risk or compliance blocks the candidate and "
           "no safe allowed revision is available, if the recommendation "
           "stabilizes, if confidence remains too low and human input is "
           "needed, if the max round count is reached, or if an "
           "approval-ready payload exists.\n"
           "11. If risk or compliance blocks the final action, report the "
           "block and do not call submit_order_batch.\n"
           "12. If checks pass and an order is warranted, call "
           "submit_order_batch with the exact validated payload. EdgeFleet "
           "will pause for human approval.\n"
           "13. Store a final loop record with every round, bull case, bear "
           "case, critiques, candidate revisions, risk review, compliance "
           "review, stopping reason, and dissenting points."
       ),
   )

Advanced operator client
~~~~~~~~~~~~~~~~~~~~~~~~

The advanced client targets ``advanced_portfolio_debate`` and passes an
explicit debate-round budget in task context. The loop is application-level
orchestration performed by the strategy coordinator through delegated agent
calls and guarded actions.

.. code-block:: python

   # run_advanced_premarket_debate.py
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
                   "Review the technology book before market open. Include "
                   "current holdings, related semiconductor names, and hedge "
                   "candidates. Run a bounded bull/bear debate before "
                   "proposing action. Do not send orders without approval."
               ),
           },
           skill="advanced_portfolio_debate",
           target_agent="trading-coordinator-agent",
           allow_actions=True,
           conversation_id="trading/pre-market/tech/advanced",
           context={
               "max_debate_rounds": 3,
               "stop_when_stable": True,
           },
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
           "Complete advanced pre-market technology debate",
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
