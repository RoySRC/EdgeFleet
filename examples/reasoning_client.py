from __future__ import annotations

import asyncio
import os

from edgefleet import (
    EdgeFleetClient,
    ReasoningConfig,
    ReasoningMode,
)


async def main() -> None:
    client = EdgeFleetClient(
        os.getenv("EDGEFLEET_URL", "http://127.0.0.1:8000"),
        token=os.getenv("EDGEFLEET_TOKEN"),
    )
    result = await client.submit(
        "Diagnose an intermittently overheating actuator.",
        skill="diagnose",
        conversation_id="actuator-maintenance",
        context={"device": "actuator-7", "site": "lab"},
        reasoning=ReasoningConfig(
            mode=ReasoningMode.PLAN_EXECUTE,
            reflection=True,
            reasoning_summary=True,
            memory=True,
            retrieval=True,
            human_approval=True,
        ),
    )
    print(result.model_dump_json(indent=2))

    if result.pending_question:
        result = await client.resume(
            result.task_id,
            human_input=input(f"{result.pending_question} "),
        )
        print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())

