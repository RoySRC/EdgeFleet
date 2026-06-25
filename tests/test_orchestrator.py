from edgefleet import EdgeAgent, Orchestrator, TaskRequest, TaskState


async def test_routes_to_local_agent_by_skill() -> None:
    agent = EdgeAgent(
        agent_id="edge-1",
        name="Edge",
        endpoint="http://edge-1:8100",
    )

    @agent.skill("inspect")
    async def inspect(task: TaskRequest):
        return {"inspected": task.input}

    orchestrator = Orchestrator(local_agents=[agent])
    await orchestrator.initialize()

    result = await orchestrator.submit(
        TaskRequest(input="part-a", skill="inspect")
    )

    assert result.state is TaskState.COMPLETED
    assert result.agent_id == "edge-1"
    assert result.output == {"inspected": "part-a"}


async def test_missing_capability_fails_cleanly() -> None:
    orchestrator = Orchestrator()

    result = await orchestrator.submit(
        TaskRequest(input="x", skill="missing")
    )

    assert result.state is TaskState.FAILED
    assert "No online agent matches" in result.error

