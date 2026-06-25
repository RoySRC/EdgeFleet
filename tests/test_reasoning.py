from pathlib import Path

import pytest

from edgefleet import (
    Action,
    ActionPolicy,
    ActionRegistry,
    Document,
    EdgeAgent,
    InMemoryRetriever,
    JsonFileRuntimeState,
    MockLLM,
    ReasoningConfig,
    ReasoningMode,
    ResumeRequest,
    TaskRequest,
    TaskState,
)
from edgefleet.llm import LLMResponse, ToolCall


@pytest.mark.parametrize(
    ("config", "responses", "trace_type", "final"),
    [
        (
            ReasoningConfig(mode=ReasoningMode.PLAN_EXECUTE),
            [
                LLMResponse(
                    content='{"steps":[{"id":"1","description":"check"}]}'
                ),
                LLMResponse(content="planned answer"),
            ],
            "plan",
            "planned answer",
        ),
        (
            ReasoningConfig(
                mode=ReasoningMode.SELF_CONSISTENCY, samples=2
            ),
            [
                LLMResponse(content="candidate a"),
                LLMResponse(content="candidate b"),
                LLMResponse(content='{"best":1,"summary":"better"}'),
                LLMResponse(content="consistent answer"),
            ],
            "self_consistency",
            "consistent answer",
        ),
        (
            ReasoningConfig(
                mode=ReasoningMode.TREE_SEARCH,
                branches=2,
                depth=1,
            ),
            [
                LLMResponse(content="branch a"),
                LLMResponse(content="branch b"),
                LLMResponse(content='{"best":0,"summary":"safer"}'),
                LLMResponse(content="tree answer"),
            ],
            "tree_search",
            "tree answer",
        ),
        (
            ReasoningConfig(mode=ReasoningMode.GRAPH_SEARCH),
            [
                LLMResponse(
                    content=(
                        '{"nodes":[{"id":"a","proposal":"inspect"}],'
                        '"edges":[]}'
                    )
                ),
                LLMResponse(content="graph route"),
                LLMResponse(content="graph answer"),
            ],
            "graph_search",
            "graph answer",
        ),
    ],
)
async def test_reasoning_modes(
    config, responses, trace_type, final
) -> None:
    agent = EdgeAgent(
        agent_id="edge",
        name="Edge",
        endpoint="http://edge",
        llm=MockLLM(responses),
    )

    result = await agent.execute(
        TaskRequest(input="solve this", reasoning=config)
    )

    assert result.state is TaskState.COMPLETED
    assert result.output == final
    assert result.trace[0]["type"] == trace_type


async def test_reflection_and_reasoning_summary() -> None:
    llm = MockLLM(
        [
            LLMResponse(content="draft"),
            LLMResponse(content="missing caveat"),
            LLMResponse(content="revised"),
            LLMResponse(content="Used evidence and checked caveats."),
        ]
    )
    agent = EdgeAgent(
        agent_id="edge",
        name="Edge",
        endpoint="http://edge",
        llm=llm,
    )

    result = await agent.execute(
        TaskRequest(
            input="answer",
            reasoning=ReasoningConfig(
                reflection=True,
                reasoning_summary=True,
            ),
        )
    )

    assert result.output == "revised"
    assert [item["type"] for item in result.trace] == [
        "reflection",
        "reasoning_summary",
    ]
    assert "hidden token-level" in result.trace[-1]["notice"]


async def test_memory_retrieval_template_and_dynamic_context() -> None:
    llm = MockLLM(
        [
            LLMResponse(content="first answer"),
            LLMResponse(content="second answer"),
        ]
    )
    retriever = InMemoryRetriever(
        [
            Document(
                id="manual",
                text="Servo AX-7 maximum temperature is 70 Celsius.",
            )
        ]
    )
    agent = EdgeAgent(
        agent_id="edge",
        name="Edge",
        endpoint="http://edge",
        llm=llm,
        retriever=retriever,
    )
    agent.prompt_skill(
        "diagnose",
        description="Diagnose equipment",
        prompt_template=(
            "Diagnose {input}. Site context: {context}. "
            "Conversation: {conversation_id}"
        ),
    )
    config = ReasoningConfig(memory=True, retrieval=True)

    first = await agent.execute(
        TaskRequest(
            input="AX-7 overheating",
            skill="diagnose",
            context={"site": "lab"},
            conversation_id="conversation-1",
            reasoning=config,
        )
    )
    second = await agent.execute(
        TaskRequest(
            input="What did you conclude?",
            skill="diagnose",
            context={"site": "lab"},
            conversation_id="conversation-1",
            reasoning=config,
        )
    )

    assert first.trace[0]["type"] == "retrieval"
    assert second.trace[0]["type"] == "memory"
    second_system = llm.calls[1]["messages"][0]["content"]
    second_user = llm.calls[1]["messages"][1]["content"]
    assert "first answer" in second_system
    assert "Site context" in second_user
    assert "conversation-1" in second_user


async def test_human_input_conversation_pause_and_resume() -> None:
    llm = MockLLM(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="human-1",
                        name="request_human_input",
                        arguments={"question": "Which bin?"},
                    )
                ]
            ),
            LLMResponse(content="Using bin B"),
        ]
    )
    agent = EdgeAgent(
        agent_id="edge",
        name="Edge",
        endpoint="http://edge",
        llm=llm,
    )
    task = TaskRequest(
        input="Place the part",
        reasoning=ReasoningConfig(human_approval=True),
    )

    paused = await agent.execute(task)
    resumed = await agent.resume(
        task.id, ResumeRequest(human_input="Bin B")
    )

    assert paused.state is TaskState.WAITING_INPUT
    assert paused.pending_question == "Which bin?"
    assert resumed.state is TaskState.COMPLETED
    assert resumed.output == "Using bin B"


async def test_automatic_delegation_and_multi_agent_debate() -> None:
    delegated: list[tuple[str, str]] = []

    async def delegate(agent_id, request, parent):
        delegated.append((agent_id, request))
        return f"{agent_id} says inspect bearings"

    delegation_llm = MockLLM(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="delegate-1",
                        name="delegate_task",
                        arguments={
                            "target_agent": "edge-2",
                            "skill": "chat",
                            "request": "Inspect likely causes",
                        },
                    )
                ]
            ),
            LLMResponse(content="Combined delegated answer"),
        ]
    )
    agent = EdgeAgent(
        agent_id="edge-1",
        name="Edge 1",
        endpoint="http://edge-1",
        llm=delegation_llm,
        delegation_handler=delegate,
    )
    delegated_result = await agent.execute(
        TaskRequest(
            input="Diagnose vibration",
            reasoning=ReasoningConfig(auto_delegate=True),
        )
    )

    assert delegated_result.output == "Combined delegated answer"
    assert delegated[0][0] == "edge-2"

    debate_llm = MockLLM(
        [
            LLMResponse(content='{"best":1,"summary":"stronger"}'),
            LLMResponse(content="Debate final"),
        ]
    )
    debate_agent = EdgeAgent(
        agent_id="moderator",
        name="Moderator",
        endpoint="http://moderator",
        llm=debate_llm,
        delegation_handler=delegate,
    )
    debate = await debate_agent.execute(
        TaskRequest(
            input="Choose inspection strategy",
            reasoning=ReasoningConfig(
                mode=ReasoningMode.DEBATE,
                debate_rounds=1,
                debate_agents=["edge-2", "edge-3"],
            ),
        )
    )

    assert debate.output == "Debate final"
    assert debate.trace[0]["type"] == "debate"
    assert len(debate.trace[0]["transcript"]) == 2


async def test_checkpoint_persists_across_agent_restart(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "agent-state.json"
    actions = ActionRegistry()
    actions.register(
        Action(
            name="move",
            description="Move",
            handler=lambda: "moved",
            policy=ActionPolicy.DANGEROUS,
        )
    )
    first_agent = EdgeAgent(
        agent_id="edge",
        name="Edge",
        endpoint="http://edge",
        llm=MockLLM(
            [
                LLMResponse(
                    tool_calls=[
                        ToolCall(
                            id="move-1",
                            name="move",
                            arguments={},
                        )
                    ]
                )
            ]
        ),
        actions=actions,
        state=JsonFileRuntimeState(state_path),
    )
    task = TaskRequest(input="move", allow_actions=True)
    paused = await first_agent.execute(task)

    second_agent = EdgeAgent(
        agent_id="edge",
        name="Edge",
        endpoint="http://edge",
        llm=MockLLM([LLMResponse(content="done")]),
        actions=actions,
        state=JsonFileRuntimeState(state_path),
    )
    resumed = await second_agent.resume(
        task.id, ResumeRequest(approved_actions={"move"})
    )

    assert paused.state is TaskState.WAITING_APPROVAL
    assert resumed.state is TaskState.COMPLETED
    assert resumed.output == "done"
