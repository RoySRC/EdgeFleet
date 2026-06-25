from __future__ import annotations

import argparse
import importlib
import os
import sys
from typing import Any

import uvicorn

from edgefleet.agent import EdgeAgent
from edgefleet.orchestrator import Orchestrator
from edgefleet.store import JsonFileStore


def _load_factory(path: str) -> Any:
    current_directory = os.getcwd()
    if current_directory not in sys.path:
        sys.path.insert(0, current_directory)
    module_name, separator, attribute = path.partition(":")
    if not separator:
        raise ValueError("Factory must use the form module:function")
    module = importlib.import_module(module_name)
    factory = getattr(module, attribute)
    return factory()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="edgefleet")
    subparsers = parser.add_subparsers(dest="command", required=True)

    orchestrator = subparsers.add_parser("orchestrator")
    orchestrator.add_argument("--host", default="0.0.0.0")
    orchestrator.add_argument("--port", type=int, default=8000)
    orchestrator.add_argument(
        "--token", default=os.getenv("EDGEFLEET_TOKEN")
    )
    orchestrator.add_argument(
        "--edge-token", default=os.getenv("EDGEFLEET_EDGE_TOKEN")
    )
    orchestrator.add_argument(
        "--state-file",
        default=os.getenv("EDGEFLEET_STATE_FILE"),
        help="Persist agents, tasks, and resumable goals to JSON.",
    )

    agent = subparsers.add_parser("agent")
    agent.add_argument(
        "--factory",
        required=True,
        help="Python factory path, for example examples.agent:create_agent",
    )
    agent.add_argument("--host", default="0.0.0.0")
    agent.add_argument("--port", type=int, default=8100)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "orchestrator":
        store = (
            JsonFileStore(args.state_file)
            if args.state_file
            else None
        )
        runtime = Orchestrator(
            token=args.token,
            edge_token=args.edge_token,
            store=store,
        )
        uvicorn.run(runtime.create_app(), host=args.host, port=args.port)
        return

    runtime = _load_factory(args.factory)
    if not isinstance(runtime, EdgeAgent):
        raise TypeError("Agent factory must return edgefleet.EdgeAgent")
    uvicorn.run(runtime.create_app(), host=args.host, port=args.port)
