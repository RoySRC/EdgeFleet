import httpx

from edgefleet import EdgeAgent, Orchestrator


async def test_api_auth_and_submission() -> None:
    agent = EdgeAgent(
        agent_id="edge-1",
        name="Edge",
        endpoint="http://edge-1:8100",
    )

    @agent.skill("echo")
    async def echo(task):
        return task.input

    orchestrator = Orchestrator(token="secret", local_agents=[agent])
    await orchestrator.initialize()
    transport = httpx.ASGITransport(app=orchestrator.create_app())

    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        unauthorized = await client.get("/v1/agents")
        assert unauthorized.status_code == 401

        response = await client.post(
            "/v1/tasks",
            headers={"Authorization": "Bearer secret"},
            json={"input": "hello", "skill": "echo"},
        )

    assert response.status_code == 200
    assert response.json()["output"] == "hello"

