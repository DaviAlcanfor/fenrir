"""fenrir CLI — a REPL over the orchestrator agent with human-in-the-loop gating."""

import asyncio
import logging
import uuid

import pyfiglet
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from fenrir.agents import build_agent

RECURSION_LIMIT = 100
BANNER = pyfiglet.figlet_format("fenrir", font="slant")


def _decide(request: dict) -> list[dict]:
    """Ask the operator to approve/reject each gated action in an interrupt."""
    decisions = []
    
    for action in request["action_requests"]:
        print(f"\n  ⚠  {action['name']}  {action.get('args', {})}")
    
        if input("  approve? [Y/n] ").strip().lower() in ("", "y", "yes"):
            decisions.append({"type": "approve"})
        else:
            reason = input("  reason (optional): ").strip()
            decisions.append({"type": "reject", "message": reason} if reason else {"type": "reject"})
    
    return decisions


async def _run(agent, text: str, config: dict) -> None:
    payload: object = {"messages": [{"role": "user", "content": text}]}
    
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

    config = {
        "configurable": { "thread_id": str(uuid.uuid4())},
        "recursion_limit": RECURSION_LIMIT
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
