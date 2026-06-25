from __future__ import annotations

import pprint
from textwrap import dedent

from examples.use_cases.catalog import UseCase


def _literal(value: object) -> str:
    return pprint.pformat(value, width=72, sort_dicts=True)


def _reasoning(case: UseCase) -> str:
    fields = [f"mode=ReasoningMode.{case.mode.upper()}"]
    if case.reflection:
        fields.append("reflection=True")
    if case.memory:
        fields.append("memory=True")
    if case.retrieval:
        fields.append("retrieval=True")
    if case.auto_delegate:
        fields.extend(
            ["auto_delegate=True", "max_delegation_depth=2"]
        )
    if case.human_approval:
        fields.append("human_approval=True")
    if case.mode == "self_consistency":
        fields.append("samples=3")
    elif case.mode == "tree_search":
        fields.extend(["branches=3", "depth=2"])
    elif case.mode == "graph_search":
        fields.append("depth=2")
    elif case.mode == "debate":
        fields.extend(
            [
                'debate_agents=["specialist-edge", "safety-edge"]',
                "debate_rounds=2",
            ]
        )
    return ",\n            ".join(fields)


def _task_program(case: UseCase) -> str:
    reasoning_lines = _reasoning(case).splitlines()
    lines = [
        "import asyncio",
        "import os",
        "",
        "from edgefleet import EdgeFleetClient, ReasoningConfig, ReasoningMode",
        "",
        "",
        "async def main() -> None:",
        "    client = EdgeFleetClient(",
        '        os.getenv("EDGEFLEET_URL", "http://127.0.0.1:8000"),',
        '        token=os.getenv("EDGEFLEET_TOKEN"),',
        "    )",
        "    result = await client.submit(",
        f"        {case.prompt!r},",
        f"        skill={case.skill!r},",
        f"        target_agent={case.target_agent!r},",
        f"        context={_literal(case.context)},",
        f"        conversation_id={case.slug!r},",
        "        reasoning=ReasoningConfig(",
    ]
    lines.extend(f"            {line}" for line in reasoning_lines)
    lines.extend(
        [
            "        ),",
            f"        allow_actions={case.allow_actions!r},",
            "    )",
        ]
    )
    if case.human_approval or case.allow_actions:
        lines.extend(
            [
                "",
                '    if result.state == "waiting_approval":',
                "        result = await client.resume(",
                "            result.task_id,",
                f"            approved_actions={{{case.skill!r}}},",
                "        )",
                '    elif result.state == "waiting_input":',
                "        result = await client.resume(",
                "            result.task_id,",
                '            human_input="Operator supplied the requested value.",',
                "        )",
            ]
        )
    lines.extend(
        [
            "    print(result.model_dump_json(indent=2))",
            "",
            "",
            "asyncio.run(main())",
        ]
    )
    return "\n".join(lines)


def _approval_program(case: UseCase) -> str:
    return dedent(
        f"""
        import asyncio
        import os

        from edgefleet import EdgeFleetClient, ReasoningConfig, ReasoningMode


        async def main() -> None:
            client = EdgeFleetClient(
                os.getenv("EDGEFLEET_URL", "http://127.0.0.1:8000"),
                token=os.getenv("EDGEFLEET_TOKEN"),
            )
            result = await client.submit(
                {case.prompt!r},
                skill={case.skill!r},
                target_agent={case.target_agent!r},
                context={_literal(case.context)},
                reasoning=ReasoningConfig(
                    mode=ReasoningMode.PLAN_EXECUTE,
                    human_approval=True,
                ),
                allow_actions=True,
            )

            if result.state == "waiting_approval":
                print(result.pending_approvals)
                result = await client.resume(
                    result.task_id,
                    approved_actions={{{case.skill!r}}},
                )
            elif result.state == "waiting_input":
                result = await client.resume(
                    result.task_id,
                    human_input=input(result.pending_question or "Input: "),
                )

            print(result.model_dump_json(indent=2))


        asyncio.run(main())
        """
    ).strip()


def _product_program(case: UseCase) -> str:
    return dedent(
        f"""
        import asyncio

        from edgefleet import (
            EdgeAgent,
            MockLLM,
            Orchestrator,
            ReasoningConfig,
            ReasoningMode,
            TaskRequest,
        )


        async def main() -> None:
            agent = EdgeAgent(
                agent_id={case.target_agent!r},
                name={case.title!r},
                endpoint="http://127.0.0.1:8100",
                llm=MockLLM(prefix={case.slug!r}),
            )
            agent.prompt_skill(
                {case.skill!r},
                description={case.title!r},
                prompt_template=(
                    "Request: {{input}}\\nContext: {{context}}\\n"
                    "Return a bounded implementation plan."
                ),
            )
            orchestrator = Orchestrator(local_agents=[agent])
            await orchestrator.initialize()
            result = await orchestrator.submit(
                TaskRequest(
                    input={case.prompt!r},
                    skill={case.skill!r},
                    context={_literal(case.context)},
                    reasoning=ReasoningConfig(
                        mode=ReasoningMode.PLAN_EXECUTE
                    ),
                )
            )
            print(result.output)


        asyncio.run(main())
        """
    ).strip()


def _research_program(case: UseCase) -> str:
    return dedent(
        f"""
        import asyncio
        import time

        from edgefleet import (
            EdgeAgent,
            MockLLM,
            ReasoningConfig,
            ReasoningMode,
            TaskRequest,
        )


        async def main() -> None:
            llm = MockLLM(prefix={case.slug!r})
            agent = EdgeAgent(
                agent_id={case.target_agent!r},
                name={case.title!r},
                endpoint="http://127.0.0.1:8100",
                llm=llm,
            )
            started = time.perf_counter()
            result = await agent.execute(
                TaskRequest(
                    input={case.prompt!r},
                    context={_literal(case.context)},
                    reasoning=ReasoningConfig(
                        mode=ReasoningMode.{case.mode.upper()},
                        samples=3,
                        reasoning_summary=True,
                    ),
                )
            )
            print({{
                "state": result.state,
                "latency_seconds": time.perf_counter() - started,
                "model_calls": len(llm.calls),
                "trace": result.trace,
            }})


        asyncio.run(main())
        """
    ).strip()


def _boundary_program(case: UseCase) -> str:
    return dedent(
        f"""
        import asyncio
        import os

        from edgefleet import EdgeFleetClient, ReasoningConfig


        async def main() -> None:
            client = EdgeFleetClient(
                os.getenv("EDGEFLEET_URL", "http://127.0.0.1:8000"),
                token=os.getenv("EDGEFLEET_TOKEN"),
            )
            result = await client.submit(
                {case.prompt!r},
                skill="supervisory_review",
                target_agent={case.target_agent!r},
                context={{
                    **{_literal(case.context)},
                    "prohibited_capability": {case.title!r},
                    "required_handoff": "validated deterministic system",
                }},
                reasoning=ReasoningConfig(reasoning_summary=True),
                allow_actions=False,
            )
            print(result.output)


        asyncio.run(main())
        """
    ).strip()


def _gateway_program(case: UseCase) -> str:
    title = case.title
    if title == "Local LLM-to-ROS 2 bridge":
        return dedent(
            """
            from control_msgs.action import GripperCommand

            from edgefleet import EdgeAgent, OpenAICompatibleLLM
            from edgefleet.integrations.ros2 import ROS2ActionAdapter


            def goal_factory(arguments):
                goal = GripperCommand.Goal()
                goal.command.position = arguments["position"]
                goal.command.max_effort = arguments["max_effort"]
                return goal


            agent = EdgeAgent(
                agent_id="robot-edge",
                name="ROS 2 robot edge",
                endpoint="http://robot-edge:8100",
                llm=OpenAICompatibleLLM(
                    model="qwen3:4b",
                    base_url="http://127.0.0.1:8080/v1",
                ),
            )
            agent.actions.register(
                ROS2ActionAdapter(
                    node_name="edgefleet_gripper",
                    action_name="/gripper_controller/gripper_cmd",
                    action_type=GripperCommand,
                    goal_factory=goal_factory,
                ).as_action(
                    name="move_gripper",
                    description="Move the gripper",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "position": {"type": "number"},
                            "max_effort": {"type": "number"},
                        },
                        "required": ["position", "max_effort"],
                    },
                )
            )
            """
        ).strip()
    if title == "LLM-to-MCP tool bridge":
        return dedent(
            """
            import asyncio

            from edgefleet import EdgeAgent, MockLLM
            from edgefleet.integrations.mcp import MCPToolProvider


            async def main() -> None:
                agent = EdgeAgent(
                    agent_id="mcp-edge",
                    name="MCP gateway",
                    endpoint="http://mcp-edge:8100",
                    llm=MockLLM(),
                )
                provider = MCPToolProvider("http://tool-server:9000/mcp")
                await provider.load_into(agent.actions)
                print([action.name for action in agent.actions.list()])


            asyncio.run(main())
            """
        ).strip()
    if title == "Native agent-to-A2A facade":
        return dedent(
            """
            import uvicorn

            from edgefleet import EdgeAgent, MockLLM
            from edgefleet.integrations.a2a import mount_a2a


            agent = EdgeAgent(
                agent_id="a2a-edge",
                name="A2A-compatible agent",
                endpoint="http://a2a-edge:8100",
                llm=MockLLM(),
            )
            app = agent.create_app()
            mount_a2a(app, agent)

            uvicorn.run(app, host="0.0.0.0", port=8100)
            """
        ).strip()
    if title == "HTTP-to-edge-device gateway":
        return dedent(
            """
            import uvicorn

            from edgefleet import EdgeAgent


            agent = EdgeAgent(
                agent_id="device-gateway",
                name="HTTP edge-device gateway",
                endpoint="http://device-gateway:8100",
                token="device-token",
            )

            @agent.skill("read_device")
            async def read_device(task):
                return {"device": task.input["device"], "status": "online"}

            uvicorn.run(agent.create_app(), host="0.0.0.0", port=8100)
            """
        ).strip()
    if title == "NATS-based agent messaging":
        return dedent(
            """
            import asyncio

            from edgefleet import EdgeAgent
            from edgefleet.integrations.nats import NATSTaskTransport


            async def main() -> None:
                agent = EdgeAgent(
                    agent_id="nats-edge",
                    name="NATS edge agent",
                    endpoint="http://nats-edge:8100",
                )
                transport = NATSTaskTransport(
                    ["nats://nats.local:4222"]
                )
                await transport.connect()
                await transport.serve(agent.agent_id, agent.execute)
                await asyncio.Event().wait()


            asyncio.run(main())
            """
        ).strip()
    if title == "LangGraph-based routing":
        return dedent(
            """
            from edgefleet import Orchestrator
            from edgefleet.routing import LangGraphRouter


            # compiled_graph.ainvoke(...) must return {"agent_id": "..."}.
            router = LangGraphRouter(compiled_graph)
            orchestrator = Orchestrator(router=router)
            app = orchestrator.create_app()
            """
        ).strip()
    if title == "OpenAI-compatible local-model abstraction":
        return dedent(
            """
            from edgefleet import EdgeAgent, OpenAICompatibleLLM


            llm = OpenAICompatibleLLM(
                model="qwen3:4b",
                base_url="http://127.0.0.1:8080/v1",
                api_key="local",
            )
            agent = EdgeAgent(
                agent_id="local-model-edge",
                name="Local model agent",
                endpoint="http://local-model-edge:8100",
                llm=llm,
            )
            """
        ).strip()
    if title == "Wrapping legacy systems as guarded actions":
        return dedent(
            """
            from edgefleet import ActionPolicy, ActionRegistry


            actions = ActionRegistry()

            @actions.action(
                "legacy_setpoint",
                description="Set a legacy controller setpoint",
                input_schema={
                    "type": "object",
                    "properties": {"value": {"type": "number"}},
                    "required": ["value"],
                    "additionalProperties": False,
                },
                policy=ActionPolicy.DANGEROUS,
            )
            async def legacy_setpoint(value: float):
                return await legacy_client.setpoint(value)
            """
        ).strip()
    return dedent(
        """
        from edgefleet import EdgeAgent, OpenAICompatibleLLM, Orchestrator


        agents = [
            EdgeAgent(
                agent_id="ollama-edge",
                name="Ollama edge",
                endpoint="http://ollama-edge:8100",
                llm=OpenAICompatibleLLM(
                    model="qwen3:4b",
                    base_url="http://ollama:11434/v1",
                ),
            ),
            EdgeAgent(
                agent_id="llamacpp-edge",
                name="llama.cpp edge",
                endpoint="http://llamacpp-edge:8100",
                llm=OpenAICompatibleLLM(
                    model="local",
                    base_url="http://llamacpp:8080/v1",
                ),
            ),
        ]
        orchestrator = Orchestrator(local_agents=agents)
        """
    ).strip()


def program_for(case: UseCase) -> str:
    if case.pattern == "approval":
        return _approval_program(case)
    if case.pattern == "gateway":
        return _gateway_program(case)
    if case.pattern == "research":
        return _research_program(case)
    if case.pattern == "product":
        return _product_program(case)
    if case.pattern == "boundary":
        return _boundary_program(case)
    return _task_program(case)
