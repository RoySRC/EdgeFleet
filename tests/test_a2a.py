import httpx

from edgefleet import EdgeAgent
from edgefleet.integrations.a2a import mount_a2a


async def test_mounts_official_a2a_card() -> None:
    agent = EdgeAgent(
        agent_id="edge-1",
        name="Edge",
        endpoint="http://edge-1:8100",
    )

    @agent.skill("echo", description="Echo input")
    async def echo(task):
        return task.input

    app = agent.create_app()
    mount_a2a(app, agent)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        response = await client.get(
            "/.well-known/a2a-agent-card.json"
        )
        message_response = await client.post(
            "/a2a",
            headers={"A2A-Version": "1.0"},
            json={
                "jsonrpc": "2.0",
                "id": "request-1",
                "method": "SendMessage",
                "params": {
                    "message": {
                        "messageId": "message-1",
                        "role": "ROLE_USER",
                        "parts": [{"text": "hello"}],
                    },
                    "metadata": {"skill": "echo"},
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["name"] == "Edge"
    assert response.json()["skills"][0]["id"] == "echo"
    assert message_response.status_code == 200
    part = message_response.json()["result"]["message"]["parts"][0]
    assert part["data"] == "hello"
