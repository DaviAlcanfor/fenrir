"""fenrir CLI — a REPL over the orchestrator agent with human-in-the-loop gating."""

import asyncio
import logging
import uuid
from typing import Final

import pyfiglet
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from fenrir.agents import FenrirAgent, build_agent
from fenrir.protocol import Decision, HumanTurn, InterruptRequest, InvokePayload

RECURSION_LIMIT: Final = 100
BANNER: Final = pyfiglet.figlet_format("fenrir", font="slant")


def _approved(answer: str) -> bool:
    return answer.strip().lower() in ("y", "yes")


def _decide(request: InterruptRequest) -> list[Decision]:
    """Ask the operator to approve/reject each gated action in an interrupt."""
    decisions: list[Decision] = []

    for action in request["action_requests"]:
        print(f"\n  ⚠  {action['name']}  {action.get('args', {})}")

        if _approved(input("  approve? [y/N] ")):
            decisions.append({"type": "approve"})
        else:
            reason = input("  reason (optional): ").strip()
            decisions.append({"type": "reject", "message": reason} if reason else {"type": "reject"})

    return decisions


async def _run(agent: FenrirAgent, text: str, config: RunnableConfig) -> None:
    turn: HumanTurn = {"role": "user", "content": text}
    payload: InvokePayload | Command = {"messages": [turn]}

    while True:
        result = await agent.ainvoke(payload, config)
        interrupts = result.get("__interrupt__")

        if not interrupts:
            print(f"\nfenrir> {result['messages'][-1].content}\n")
            return

        payload = Command(resume={"decisions": _decide(interrupts[0].value)})


async def _amain() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        agent = await build_agent(checkpointer=InMemorySaver())
    except Exception as e:
        raise SystemExit(f"could not start fenrir: {e}\nset your keys in .env (see .env.example)") from e

    config: RunnableConfig = {
        "configurable": {"thread_id": str(uuid.uuid4())},
        "recursion_limit": RECURSION_LIMIT,
    }

    print(BANNER)
    print("bug bounty assistant — point it at a scope.md. Ctrl-C to quit.\n")

    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if text in ("exit", "quit"):
            return
        if not text:
            continue

        try:
            await _run(agent, text, config)
        except KeyboardInterrupt:
            print("\n[interrupted]\n")


def main() -> None:
    asyncio.run(_amain())
