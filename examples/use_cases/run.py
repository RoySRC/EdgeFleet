from __future__ import annotations

import argparse
import asyncio
import os

from edgefleet import EdgeFleetClient, ReasoningConfig, ReasoningMode

from examples.use_cases.catalog import USE_CASES_BY_SLUG


async def execute(slug: str) -> None:
    case = USE_CASES_BY_SLUG[slug]
    client = EdgeFleetClient(
        os.getenv("EDGEFLEET_URL", "http://127.0.0.1:8000"),
        token=os.getenv("EDGEFLEET_TOKEN"),
    )
    result = await client.submit(
        case.prompt,
        skill=case.skill,
        target_agent=case.target_agent,
        context=case.context,
        conversation_id=case.slug,
        reasoning=ReasoningConfig(
            mode=ReasoningMode(case.mode),
            reflection=case.reflection,
            memory=case.memory,
            retrieval=case.retrieval,
            auto_delegate=case.auto_delegate,
            human_approval=case.human_approval,
        ),
        allow_actions=case.allow_actions,
    )
    print(result.model_dump_json(indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an EdgeFleet use-case catalog entry."
    )
    parser.add_argument("slug", nargs="?")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available use-case slugs.",
    )
    args = parser.parse_args()
    if args.list:
        for slug in sorted(USE_CASES_BY_SLUG):
            print(slug)
        return
    if not args.slug:
        parser.error("provide a slug or use --list")
    if args.slug not in USE_CASES_BY_SLUG:
        parser.error(
            f"unknown slug {args.slug!r}; use --list to inspect choices"
        )
    asyncio.run(execute(args.slug))


if __name__ == "__main__":
    main()
