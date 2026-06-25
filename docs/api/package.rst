Top-level package
=================

``edgefleet`` re-exports the primary application-facing classes. Canonical
API definitions are documented on their module pages to avoid duplicate
object targets.

Public convenience imports
--------------------------

* Actions: :class:`edgefleet.actions.Action`,
  :class:`edgefleet.actions.ActionPolicy`, and
  :class:`edgefleet.actions.ActionRegistry`
* Runtime: :class:`edgefleet.agent.EdgeAgent` and
  :class:`edgefleet.orchestrator.Orchestrator`
* Client: :class:`edgefleet.client.EdgeFleetClient`
* Models: :class:`edgefleet.models.TaskRequest`,
  :class:`edgefleet.models.TaskResult`,
  :class:`edgefleet.models.ReasoningConfig`, and
  :class:`edgefleet.models.ReasoningMode`
* LLMs: :class:`edgefleet.llm.LLMBackend`,
  :class:`edgefleet.llm.OpenAICompatibleLLM`, and
  :class:`edgefleet.llm.MockLLM`
* State: :class:`edgefleet.state.InMemoryRuntimeState`,
  :class:`edgefleet.state.JsonFileRuntimeState`,
  :class:`edgefleet.store.InMemoryStore`, and
  :class:`edgefleet.store.JsonFileStore`
* Retrieval: :class:`edgefleet.retrieval.Retriever` and
  :class:`edgefleet.retrieval.InMemoryRetriever`
