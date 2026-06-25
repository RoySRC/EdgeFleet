from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from edgefleet.llm import LLMBackend, ToolCall
from edgefleet.models import (
    ApprovalRequest,
    ConversationMessage,
    ReasoningMode,
    TaskRequest,
    TaskState,
)
from edgefleet.prompts import PromptBuilder, PromptContext
from edgefleet.retrieval import Retriever
from edgefleet.state import ExecutionCheckpoint, RuntimeStateStore

ToolProvider = Callable[[TaskRequest], list[dict[str, Any]]]
ToolExecutor = Callable[[ToolCall, TaskRequest], Awaitable[Any]]
ApprovalChecker = Callable[
    [ToolCall, TaskRequest], ApprovalRequest | None
]
Delegate = Callable[[str, str, TaskRequest], Awaitable[Any]]


@dataclass(slots=True)
class ReasoningOutcome:
    output: Any = None
    trace: list[dict[str, Any]] = field(default_factory=list)
    state: TaskState = TaskState.COMPLETED
    approvals: list[ApprovalRequest] = field(default_factory=list)
    question: str | None = None


class ReasoningEngine:
    def __init__(
        self,
        *,
        llm: LLMBackend,
        prompt_builder: PromptBuilder,
        state: RuntimeStateStore,
        tool_provider: ToolProvider,
        tool_executor: ToolExecutor,
        approval_checker: ApprovalChecker,
        retriever: Retriever | None = None,
        delegate: Delegate | None = None,
        max_tool_rounds: int = 4,
    ) -> None:
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.state = state
        self.tool_provider = tool_provider
        self.tool_executor = tool_executor
        self.approval_checker = approval_checker
        self.retriever = retriever
        self.delegate = delegate
        self.max_tool_rounds = max_tool_rounds

    async def run(self, task: TaskRequest) -> ReasoningOutcome:
        prompt = await self._build_prompt(task)
        memory = prompt.memory
        documents = prompt.documents
        trace: list[dict[str, Any]] = []
        if memory:
            trace.append(
                {"type": "memory", "messages_loaded": len(memory)}
            )
        if documents:
            trace.append(
                {
                    "type": "retrieval",
                    "documents": [
                        {
                            "id": document.id,
                            "metadata": document.metadata,
                        }
                        for document in documents
                    ],
                }
            )

        preparation = await self._prepare(task, prompt, trace)
        messages = [
            {"role": "system", "content": prompt.system},
            {
                "role": "user",
                "content": self._execution_prompt(
                    prompt.user, preparation
                ),
            },
        ]
        outcome = await self._tool_loop(task, messages, trace)
        if outcome.state is not TaskState.COMPLETED:
            return outcome

        output = outcome.output
        if task.reasoning.reflection:
            output = await self._reflect(prompt, output, outcome.trace)

        if task.reasoning.reasoning_summary:
            summary = await self._reasoning_summary(
                prompt.user, output, outcome.trace
            )
            outcome.trace.append(
                {
                    "type": "reasoning_summary",
                    "summary": summary,
                    "notice": (
                        "Concise decision summary; hidden token-level "
                        "reasoning is not collected."
                    ),
                }
            )

        outcome.output = output
        if task.reasoning.memory and task.conversation_id:
            await self.state.append_memory(
                task.conversation_id,
                ConversationMessage(role="user", content=task.input),
            )
            await self.state.append_memory(
                task.conversation_id,
                ConversationMessage(role="assistant", content=output),
            )
        return outcome

    async def resume(
        self,
        task_id: str,
        *,
        approved_actions: set[str],
        human_input: str | None,
    ) -> ReasoningOutcome:
        checkpoint = await self.state.get_checkpoint(task_id)
        if checkpoint is None:
            raise LookupError(f"No resumable checkpoint for task: {task_id}")

        task = checkpoint.task.model_copy(deep=True)
        task.approved_actions.update(approved_actions)
        checkpoint.task = task
        if human_input is not None:
            checkpoint.human_input = human_input
        effective_human_input = checkpoint.human_input
        messages = list(checkpoint.messages)
        trace = list(checkpoint.trace)
        pending_calls = [
            ToolCall(
                id=item["id"],
                name=item["name"],
                arguments=item.get("arguments", {}),
            )
            for item in checkpoint.pending_tool_calls
        ]
        if (
            any(call.name == "request_human_input" for call in pending_calls)
            and effective_human_input is None
        ):
            await self.state.save_checkpoint(task_id, checkpoint)
            return ReasoningOutcome(
                state=TaskState.WAITING_INPUT,
                trace=trace,
                question=checkpoint.question,
            )
        approvals = [
            approval
            for call in pending_calls
            if call.name != "request_human_input"
            and (approval := self.approval_checker(call, task)) is not None
        ]
        if approvals:
            await self.state.save_checkpoint(task_id, checkpoint)
            return ReasoningOutcome(
                state=TaskState.WAITING_APPROVAL,
                trace=trace,
                approvals=approvals,
            )

        assistant_message = checkpoint.assistant_message
        if assistant_message is not None:
            messages.append(assistant_message)
        for call in pending_calls:
            if call.name == "request_human_input":
                result: Any = {"response": effective_human_input}
            else:
                result = await self.tool_executor(call, task)
            trace.append(
                {
                    "type": "tool",
                    "name": call.name,
                    "arguments": call.arguments,
                    "result": result,
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, default=str),
                }
            )
        await self.state.delete_checkpoint(task_id)
        outcome = await self._tool_loop(task, messages, trace)
        if outcome.state is TaskState.COMPLETED:
            prompt = await self._build_prompt(task)
            if task.reasoning.reflection:
                outcome.output = await self._reflect(
                    prompt, outcome.output, outcome.trace
                )
            if task.reasoning.reasoning_summary:
                summary = await self._reasoning_summary(
                    prompt.user, outcome.output, outcome.trace
                )
                outcome.trace.append(
                    {
                        "type": "reasoning_summary",
                        "summary": summary,
                        "notice": (
                            "Concise decision summary; hidden token-level "
                            "reasoning is not collected."
                        ),
                    }
                )
        if (
            outcome.state is TaskState.COMPLETED
            and task.reasoning.memory
            and task.conversation_id
        ):
            await self.state.append_memory(
                task.conversation_id,
                ConversationMessage(role="user", content=task.input),
            )
            await self.state.append_memory(
                task.conversation_id,
                ConversationMessage(
                    role="assistant", content=outcome.output
                ),
            )
        return outcome

    async def _build_prompt(self, task: TaskRequest) -> PromptContext:
        memory = []
        if task.reasoning.memory and task.conversation_id:
            memory = await self.state.get_memory(task.conversation_id)
        documents = []
        if task.reasoning.retrieval and self.retriever is not None:
            query = (
                task.input
                if isinstance(task.input, str)
                else json.dumps(task.input, default=str)
            )
            documents = await self.retriever.search(
                query, limit=task.reasoning.retrieval_limit
            )
        return self.prompt_builder.build(
            task, memory=memory, documents=documents
        )

    async def _prepare(
        self,
        task: TaskRequest,
        prompt: PromptContext,
        trace: list[dict[str, Any]],
    ) -> str:
        mode = task.reasoning.mode
        if mode is ReasoningMode.DIRECT:
            return ""
        if mode is ReasoningMode.PLAN_EXECUTE:
            response = await self._ask(
                prompt,
                "Create a concise, executable plan for the request. Return "
                'JSON: {"steps":[{"id":"1","description":"...","success_'
                'criteria":"..."}],"risks":["..."]}. Do not execute tools.',
            )
            plan = _parse_json(response) or {"plan": response}
            trace.append({"type": "plan", "plan": plan})
            return "Use this plan as guidance, adapting if observations require it:\n" + json.dumps(
                plan, indent=2
            )
        if mode is ReasoningMode.SELF_CONSISTENCY:
            return await self._self_consistency(task, prompt, trace)
        if mode is ReasoningMode.TREE_SEARCH:
            return await self._tree_search(task, prompt, trace)
        if mode is ReasoningMode.GRAPH_SEARCH:
            return await self._graph_search(task, prompt, trace)
        if mode is ReasoningMode.DEBATE:
            return await self._debate(task, prompt, trace)
        return ""

    async def _self_consistency(
        self,
        task: TaskRequest,
        prompt: PromptContext,
        trace: list[dict[str, Any]],
    ) -> str:
        candidates = []
        for index in range(task.reasoning.samples):
            candidates.append(
                await self._ask(
                    prompt,
                    "Produce an independent candidate solution. State the "
                    "answer and a short justification. Do not call tools. "
                    f"Candidate number: {index + 1}.",
                )
            )
        judge = await self._judge(
            prompt,
            candidates,
            "Select the most correct and robust candidate.",
        )
        trace.append(
            {
                "type": "self_consistency",
                "candidates": candidates,
                "selection": judge,
            }
        )
        best = _selected(candidates, judge)
        return f"Independent candidates were compared. Preferred proposal:\n{best}"

    async def _tree_search(
        self,
        task: TaskRequest,
        prompt: PromptContext,
        trace: list[dict[str, Any]],
    ) -> str:
        path: list[str] = []
        levels: list[dict[str, Any]] = []
        for depth in range(task.reasoning.depth):
            branches = []
            path_text = "\n".join(path) or "(root)"
            for branch in range(task.reasoning.branches):
                branches.append(
                    await self._ask(
                        prompt,
                        "Propose one distinct next approach from the current "
                        f"path. Depth={depth + 1}, branch={branch + 1}.\n"
                        f"Current path:\n{path_text}",
                    )
                )
            decision = await self._judge(
                prompt,
                branches,
                "Choose the branch most likely to solve the request safely.",
            )
            chosen = _selected(branches, decision)
            path.append(chosen)
            levels.append(
                {
                    "depth": depth + 1,
                    "branches": branches,
                    "selection": decision,
                }
            )
        trace.append(
            {"type": "tree_search", "levels": levels, "path": path}
        )
        return "Selected reasoning path:\n" + "\n".join(path)

    async def _graph_search(
        self,
        task: TaskRequest,
        prompt: PromptContext,
        trace: list[dict[str, Any]],
    ) -> str:
        graph_response = await self._ask(
            prompt,
            "Model the solution space as a small directed graph. Return JSON "
            'with "nodes" (id, proposal, score_hint) and "edges" (from, to, '
            'reason). Include converging or reusable ideas where useful. Do '
            "not call tools.",
        )
        graph = _parse_json(graph_response) or {"raw": graph_response}
        synthesis = await self._ask(
            prompt,
            "Choose and synthesize the strongest route through this proposal "
            f"graph:\n{json.dumps(graph, indent=2)}",
        )
        trace.append(
            {
                "type": "graph_search",
                "graph": graph,
                "synthesis": synthesis,
            }
        )
        return f"Selected graph synthesis:\n{synthesis}"

    async def _debate(
        self,
        task: TaskRequest,
        prompt: PromptContext,
        trace: list[dict[str, Any]],
    ) -> str:
        participants = task.reasoning.debate_agents
        transcript: list[dict[str, Any]] = []
        latest: list[str] = []
        for round_number in range(task.reasoning.debate_rounds):
            latest = []
            if participants and self.delegate is not None:
                for agent_id in participants:
                    response = await self.delegate(
                        agent_id,
                        (
                            f"Debate round {round_number + 1}. Request:\n"
                            f"{prompt.user}\nPrior transcript:\n"
                            f"{json.dumps(transcript, default=str)}\n"
                            "Give a concise position and challenge weak "
                            "assumptions."
                        ),
                        task,
                    )
                    text = (
                        response
                        if isinstance(response, str)
                        else json.dumps(response, default=str)
                    )
                    latest.append(text)
                    transcript.append(
                        {
                            "round": round_number + 1,
                            "participant": agent_id,
                            "position": text,
                        }
                    )
            else:
                personas = [
                    "pragmatic implementer",
                    "skeptical safety reviewer",
                    "systems architect",
                ]
                for persona in personas:
                    text = await self._ask(
                        prompt,
                        f"Act as a {persona}. Debate round "
                        f"{round_number + 1}. Review the prior transcript and "
                        "give a concise position:\n"
                        f"{json.dumps(transcript, default=str)}",
                    )
                    latest.append(text)
                    transcript.append(
                        {
                            "round": round_number + 1,
                            "participant": persona,
                            "position": text,
                        }
                    )
        decision = await self._judge(
            prompt,
            latest or [prompt.user],
            "Resolve the debate into one implementable answer.",
        )
        trace.append(
            {
                "type": "debate",
                "transcript": transcript,
                "decision": decision,
            }
        )
        return "Debate resolution:\n" + _selected(
            latest or [prompt.user], decision
        )

    async def _tool_loop(
        self,
        task: TaskRequest,
        messages: list[dict[str, Any]],
        trace: list[dict[str, Any]],
    ) -> ReasoningOutcome:
        tools = self.tool_provider(task)
        for _ in range(self.max_tool_rounds + 1):
            response = await self.llm.chat(messages, tools=tools or None)
            if not response.tool_calls:
                return ReasoningOutcome(
                    output=response.content,
                    trace=trace,
                )

            assistant_message = _assistant_message(
                response.content, response.tool_calls
            )
            approvals = [
                approval
                for call in response.tool_calls
                if (approval := self.approval_checker(call, task))
                is not None
            ]
            human_call = next(
                (
                    call
                    for call in response.tool_calls
                    if call.name == "request_human_input"
                ),
                None,
            )
            if approvals or human_call:
                checkpoint = ExecutionCheckpoint(
                    task=task,
                    messages=messages,
                    trace=trace,
                    pending_tool_calls=[
                        {
                            "id": call.id,
                            "name": call.name,
                            "arguments": call.arguments,
                        }
                        for call in response.tool_calls
                    ],
                    assistant_message=assistant_message,
                    kind="human_input" if human_call else "approval",
                    question=(
                        str(human_call.arguments.get("question"))
                        if human_call
                        else None
                    ),
                )
                await self.state.save_checkpoint(task.id, checkpoint)
                return ReasoningOutcome(
                    state=(
                        TaskState.WAITING_INPUT
                        if human_call
                        else TaskState.WAITING_APPROVAL
                    ),
                    trace=trace,
                    approvals=approvals,
                    question=checkpoint.question,
                )

            messages.append(assistant_message)
            for call in response.tool_calls:
                result = await self.tool_executor(call, task)
                trace.append(
                    {
                        "type": "tool",
                        "name": call.name,
                        "arguments": call.arguments,
                        "result": result,
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, default=str),
                    }
                )
        raise RuntimeError("Maximum tool-call rounds exceeded")

    async def _reflect(
        self,
        prompt: PromptContext,
        draft: Any,
        trace: list[dict[str, Any]],
    ) -> str:
        draft_text = (
            draft if isinstance(draft, str) else json.dumps(draft, default=str)
        )
        critique = await self._ask(
            prompt,
            "Critique this draft for correctness, omissions, unsupported "
            f"claims, and safety. Be concise:\n{draft_text}",
        )
        revision = await self._ask(
            prompt,
            "Revise the draft using the critique. Return only the improved "
            f"answer.\nDraft:\n{draft_text}\nCritique:\n{critique}",
        )
        trace.append(
            {
                "type": "reflection",
                "critique": critique,
                "revised": True,
            }
        )
        return revision

    async def _reasoning_summary(
        self,
        request: str,
        output: Any,
        trace: list[dict[str, Any]],
    ) -> str:
        trace_types = [item.get("type", "unknown") for item in trace]
        response = await self.llm.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Produce a concise decision summary. Do not provide "
                        "hidden chain-of-thought or token-by-token reasoning."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Request: {request}\nMethods used: {trace_types}\n"
                        f"Final answer: {output}"
                    ),
                },
            ]
        )
        return response.content or ""

    async def _ask(
        self, prompt: PromptContext, instruction: str
    ) -> str:
        response = await self.llm.chat(
            [
                {"role": "system", "content": prompt.system},
                {
                    "role": "user",
                    "content": f"{prompt.user}\n\n{instruction}",
                },
            ]
        )
        return response.content or ""

    async def _judge(
        self,
        prompt: PromptContext,
        candidates: list[str],
        instruction: str,
    ) -> dict[str, Any]:
        response = await self._ask(
            prompt,
            f"{instruction}\nCandidates:\n"
            + json.dumps(
                [
                    {"index": index, "content": candidate}
                    for index, candidate in enumerate(candidates)
                ],
                indent=2,
            )
            + '\nReturn JSON: {"best":0,"summary":"why"}.',
        )
        parsed = _parse_json(response)
        return parsed if isinstance(parsed, dict) else {
            "best": 0,
            "summary": response,
        }

    @staticmethod
    def _execution_prompt(user: str, preparation: str) -> str:
        if not preparation:
            return user
        return (
            f"{user}\n\nPre-execution reasoning artifact:\n{preparation}\n\n"
            "Now produce the final answer. Use available tools when current "
            "external information or an action is required."
        )


def _assistant_message(
    content: str | None, calls: list[ToolCall]
) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments),
                },
            }
            for call in calls
        ],
    }


def _selected(candidates: list[str], decision: dict[str, Any]) -> str:
    try:
        index = int(decision.get("best", 0))
    except (TypeError, ValueError):
        index = 0
    if not 0 <= index < len(candidates):
        index = 0
    return candidates[index]


def _parse_json(value: str) -> Any:
    value = value.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", value, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
