from pathlib import Path

from edgefleet import (
    Action,
    ActionPolicy,
    ActionRegistry,
    EdgeAgent,
    MockLLM,
    Orchestrator,
    ResumeRequest,
    TaskRequest,
)
from edgefleet.llm import LLMResponse, ToolCall
from edgefleet.models import GoalRequest, GoalState
from edgefleet.store import JsonFileStore


async def test_goal_is_persisted_and_reloadable(tmp_path: Path) -> None:
    path = tmp_path / "orchestrator.json"
    agent = EdgeAgent(
        agent_id="edge",
        name="Edge",
        endpoint="http://edge",
    )

    @agent.skill("inspect")
    async def inspect(task):
        return {"status": "ok"}

    orchestrator = Orchestrator(
        store=JsonFileStore(path), local_agents=[agent]
    )
    await orchestrator.initialize()
    goal = await orchestrator.create_goal(
        GoalRequest(
            objective="Inspect the component",
            task=TaskRequest(input="part", skill="inspect"),
        )
    )

    reloaded = JsonFileStore(path)
    stored = await reloaded.get_goal(goal.id)

    assert goal.state is GoalState.COMPLETED
    assert stored is not None
    assert stored.result.output == {"status": "ok"}


async def test_goal_resumes_after_action_approval() -> None:
    actions = ActionRegistry()
    actions.register(
        Action(
            name="move_camera",
            description="Move camera",
            handler=lambda: {"position": "inspection"},
            policy=ActionPolicy.CONTROLLED,
        )
    )
    agent = EdgeAgent(
        agent_id="edge",
        name="Edge",
        endpoint="http://edge",
        actions=actions,
        llm=MockLLM(
            [
                LLMResponse(
                    tool_calls=[
                        ToolCall(
                            id="move-1",
                            name="move_camera",
                            arguments={},
                        )
                    ]
                ),
                LLMResponse(content="Inspection complete"),
            ]
        ),
    )
    orchestrator = Orchestrator(local_agents=[agent])
    await orchestrator.initialize()

    goal = await orchestrator.create_goal(
        GoalRequest(
            objective="Inspect the component",
            task=TaskRequest(
                input="Inspect it",
                allow_actions=True,
            ),
        )
    )
    initial_state = goal.state
    resumed = await orchestrator.resume_goal(
        goal.id,
        ResumeRequest(approved_actions={"move_camera"}),
    )

    assert initial_state is GoalState.WAITING_APPROVAL
    assert resumed.state is GoalState.COMPLETED
    assert resumed.result.output == "Inspection complete"
