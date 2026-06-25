from edgefleet import (
    Action,
    ActionPolicy,
    ActionRegistry,
    EdgeAgent,
    MockLLM,
    ResumeRequest,
    TaskRequest,
    TaskState,
)
from edgefleet.llm import LLMResponse, ToolCall


async def test_direct_skill() -> None:
    agent = EdgeAgent(
        agent_id="edge-1",
        name="Edge",
        endpoint="http://edge-1:8100",
    )

    @agent.skill("echo")
    async def echo(task: TaskRequest):
        return task.input

    result = await agent.execute(TaskRequest(input="hello", skill="echo"))

    assert result.state is TaskState.COMPLETED
    assert result.output == "hello"


async def test_llm_can_execute_safe_action() -> None:
    actions = ActionRegistry()
    actions.register(
        Action(
            name="temperature",
            description="Read temperature",
            handler=lambda: {"celsius": 25},
            policy=ActionPolicy.SAFE,
        )
    )
    llm = MockLLM(
        responses=[
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="temperature",
                        arguments={},
                    )
                ]
            ),
            LLMResponse(content="It is 25 C"),
        ]
    )
    agent = EdgeAgent(
        agent_id="edge-1",
        name="Edge",
        endpoint="http://edge-1:8100",
        llm=llm,
        actions=actions,
    )

    result = await agent.execute(
        TaskRequest(input="temperature?", allow_actions=True)
    )

    assert result.state is TaskState.COMPLETED
    assert result.output == "It is 25 C"
    assert result.trace[0]["name"] == "temperature"


async def test_controlled_action_pauses_for_approval_and_resumes() -> None:
    actions = ActionRegistry()
    actions.register(
        Action(
            name="move",
            description="Move hardware",
            handler=lambda: "moved",
            policy=ActionPolicy.CONTROLLED,
        )
    )
    llm = MockLLM(
        responses=[
            LLMResponse(
                tool_calls=[
                    ToolCall(id="call-1", name="move", arguments={})
                ]
            ),
            LLMResponse(content="Movement completed"),
        ]
    )
    agent = EdgeAgent(
        agent_id="edge-1",
        name="Edge",
        endpoint="http://edge-1:8100",
        llm=llm,
        actions=actions,
    )

    result = await agent.execute(
        TaskRequest(input="move", allow_actions=True)
    )

    assert result.state is TaskState.WAITING_APPROVAL
    assert result.pending_approvals[0].action == "move"

    resumed = await agent.resume(
        result.task_id,
        ResumeRequest(approved_actions={"move"}),
    )

    assert resumed.state is TaskState.COMPLETED
    assert resumed.output == "Movement completed"
    assert resumed.trace[0]["result"] == "moved"
