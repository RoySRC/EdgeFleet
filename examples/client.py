from __future__ import annotations

import asyncio
import os

from edgefleet import EdgeFleetClient


async def main() -> None:
    client = EdgeFleetClient(
        os.getenv("EDGEFLEET_URL", "http://127.0.0.1:8000"),
        token=os.getenv("EDGEFLEET_TOKEN"),
    )
    result = await client.submit(
        {"message": "hello from the client"},
        skill="echo",
    )
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())

