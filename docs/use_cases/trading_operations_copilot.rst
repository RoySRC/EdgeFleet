Trading operations cookbooks
============================

The trading operations example is split into two cookbooks so the base system
and the advanced extension can be read independently.

Both use the same core boundary: EdgeFleet coordinates private analysis and
approval-gated broker actions, but deterministic systems own market data,
positions, risk, compliance, order validation, audit logging, and broker state.

.. toctree::
   :maxdepth: 1

   trading_base_cookbook
   trading_advanced_cookbook
