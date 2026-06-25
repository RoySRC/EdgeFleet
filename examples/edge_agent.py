from __future__ import annotations

import os

from edgefleet import (
    ActionPolicy,
    ActionRegistry,
    Document,
    EdgeAgent,
    InMemoryRetriever,
    JsonFileRuntimeState,
    OpenAICompatibleLLM,
)


def create_agent() -> EdgeAgent:
    actions = ActionRegistry()
    retriever = InMemoryRetriever(
        [
            Document(
                id="device-safety",
                text=(
                    "The simulated indicator supports red, green, and blue. "
                    "Physical robot actions require independent hardware "
                    "limits and emergency-stop systems."
                ),
            )
        ]
    )

    @actions.action(
        "read_temperature",
        description="Read a simulated temperature sensor in Celsius.",
        policy=ActionPolicy.SAFE,
    )
    async def read_temperature() -> dict[str, float]:
        return {"celsius": 24.5}

    @actions.action(
        "set_indicator",
        description="Set a simulated device indicator.",
        input_schema={
            "type": "object",
            "properties": {
                "color": {
                    "type": "string",
                    "enum": ["red", "green", "blue"],
                }
            },
            "required": ["color"],
            "additionalProperties": False,
        },
        policy=ActionPolicy.CONTROLLED,
    )
    async def set_indicator(color: str) -> dict[str, str]:
        return {"indicator": color}

    llm = OpenAICompatibleLLM(
        model=os.getenv("EDGEFLEET_MODEL", "qwen3:1.7b"),
        base_url=os.getenv(
            "EDGEFLEET_LLM_URL", "http://127.0.0.1:11434/v1"
        ),
        api_key=os.getenv("EDGEFLEET_LLM_API_KEY", "local"),
    )
    agent = EdgeAgent(
        agent_id=os.getenv("EDGEFLEET_AGENT_ID", "edge-1"),
        name=os.getenv("EDGEFLEET_AGENT_NAME", "Example edge agent"),
        endpoint=os.getenv(
            "EDGEFLEET_AGENT_ENDPOINT", "http://127.0.0.1:8100"
        ),
        description="Local LLM with simulated sensor and indicator actions",
        llm=llm,
        actions=actions,
        retriever=retriever,
        state=(
            JsonFileRuntimeState(os.environ["EDGEFLEET_AGENT_STATE"])
            if os.getenv("EDGEFLEET_AGENT_STATE")
            else None
        ),
        token=os.getenv("EDGEFLEET_EDGE_TOKEN"),
        orchestrator_url=os.getenv("EDGEFLEET_ORCHESTRATOR_URL"),
        orchestrator_token=os.getenv("EDGEFLEET_TOKEN"),
    )

    @agent.skill(
        "echo",
        description="Return the supplied input without invoking the LLM.",
        tags=["diagnostic"],
    )
    async def echo(task):
        return {"echo": task.input, "agent": agent.agent_id}

    agent.prompt_skill(
        "diagnose",
        description="Diagnose an edge-device issue using local context.",
        prompt_template=(
            "Diagnose this device issue: {input}\n"
            "Deployment context: {context}\n"
            "Return likely causes, checks, and safe next actions."
        ),
    )

    return agent
