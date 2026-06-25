Memory and retrieval
====================

Conversation memory
-------------------

Memory is enabled per task:

.. code-block:: python

   result = await client.submit(
       "What did the previous inspection find?",
       conversation_id="robot-7-maintenance",
       reasoning=ReasoningConfig(memory=True),
   )

When enabled, the agent:

1. loads recent messages for ``conversation_id``;
2. includes them in the system context;
3. appends the user input and completed answer.

Memory is not loaded for deterministic skill handlers because those handlers
receive the full task and can implement their own state policy.

Runtime state implementations
-----------------------------

In-memory:

.. code-block:: python

   from edgefleet import InMemoryRuntimeState

   state = InMemoryRuntimeState()

Persistent JSON:

.. code-block:: python

   from edgefleet import JsonFileRuntimeState

   state = JsonFileRuntimeState("/var/lib/edgefleet/agent.json")

The JSON implementation uses atomic file replacement and assumes one writer
process. It stores conversation messages and paused execution checkpoints.

Retrieval
---------

The built-in retriever provides dependency-free TF-IDF similarity:

.. code-block:: python

   from edgefleet import Document, InMemoryRetriever

   retriever = InMemoryRetriever(
       [
           Document(
               id="ax7-limits",
               text="AX-7 maximum continuous temperature is 70 Celsius.",
               metadata={"source": "service manual"},
           )
       ]
   )

   agent = EdgeAgent(..., retriever=retriever)

Enable retrieval on a task:

.. code-block:: python

   ReasoningConfig(
       retrieval=True,
       retrieval_limit=4,
   )

Retrieved text is explicitly described to the model as context rather than
instructions. This reduces, but does not eliminate, prompt-injection risk.

Custom retrievers
-----------------

Implement :class:`~edgefleet.retrieval.Retriever`:

.. code-block:: python

   class VectorRetriever(Retriever):
       async def search(self, query: str, *, limit: int = 4):
           rows = await vector_database.search(query, limit=limit)
           return [
               Document(id=row.id, text=row.text, metadata=row.metadata)
               for row in rows
           ]

For larger corpora, use embeddings and a local or remote vector store. Keep
source attribution in document metadata and apply authorization filters before
retrieval.

Data management
---------------

Conversation and retrieval data may contain sensitive operational details.
Define retention, encryption, deletion, and tenant-isolation policies before
production deployment.

