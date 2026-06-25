EdgeFleet
=========

EdgeFleet is a Python runtime for coordinating local-LLM agents on edge
devices. It provides a single task API while keeping inference, networking,
reasoning strategies, and physical-device control replaceable.

The project supports deterministic skills, local OpenAI-compatible models,
structured tool calling, multi-agent communication, prompt-based reasoning,
resumable approvals, persistent goals, and adapters for robotics and agent
protocols.

.. important::

   EdgeFleet is an orchestration layer. It is not a real-time controller or a
   replacement for hardware interlocks, collision checking, watchdogs, force
   limits, or emergency-stop systems.

Start here
----------

* :doc:`installation`
* :doc:`quickstart`
* :doc:`architecture`
* :doc:`reasoning`
* :doc:`security`

Documentation
-------------

.. toctree::
   :maxdepth: 2
   :caption: Introduction

   overview
   installation
   quickstart
   architecture
   configuration
   cli

.. toctree::
   :maxdepth: 2
   :caption: Core concepts

   tasks
   agents
   reasoning
   memory_retrieval
   approvals_goals
   multi_agent

.. toctree::
   :maxdepth: 2
   :caption: Use-case cookbook

   use_cases/index

.. toctree::
   :maxdepth: 2
   :caption: Integrations

   integrations/index

.. toctree::
   :maxdepth: 2
   :caption: Operations

   deployment
   security
   testing

.. toctree::
   :maxdepth: 2
   :caption: Reference

   api/index

Indices
-------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
