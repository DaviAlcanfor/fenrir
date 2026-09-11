"""Behavior evals for fenrir's agents — real LLM calls, mocked HexStrike tools.

Each scenario in evals/scenarios/ gets its own scope.md and a fake tool
belt, then a real agent runs against it and a scenario-specific check()
decides pass/fail from the final graph state. This costs real (free-tier)
API calls and takes real wall-clock time — it is NOT part of tests/ (which
must stay fast and free) and is meant to be run manually:

    uv run python evals/runner.py                          # every scenario
    uv run python evals/runner.py refuses_out_of_scope      # just one
"""

import asyncio
import importlib
import os
import sys
import uuid
from collections.abc import Callable, Coroutine
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

from langchain_core.runnables import RunnableConfig  # noqa: E402
from langchain_core.tools import BaseTool  # noqa: E402
from langgraph.types import Command  # noqa: E402

from evals.results import EvalResult, RunResult  # noqa: E402
from fenrir.agents import build_agent  # noqa: E402
from fenrir.config import ROOT  # noqa: E402

SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"
SCOPE_FILE = ROOT / "scope.md"
RECURSION_LIMIT = 100


def _list_scenarios() -> list[str]:
    return sorted(p.stem for p in SCENARIOS_DIR.glob("*.py") if p.stem != "__init__")


def _fake_hexstrike_tools(scenario: ModuleType) -> Callable[[], Coroutine[Any, Any, list[BaseTool]]]:
    tools = scenario.fake_tools() if hasattr(scenario, "fake_tools") else []

    async def hexstrike_tools() -> list[BaseTool]:
        return tools

    return hexstrike_tools


async def _run_scenario(scenario: ModuleType) -> EvalResult:
    if SCOPE_FILE.exists():
        raise RuntimeError(f"refusing to overwrite a real scope.md at {SCOPE_FILE} — remove it first")

    SCOPE_FILE.write_text(scenario.SCOPE_MD, encoding="utf-8")

    try:
        with patch("fenrir.agents.orchestrator.hexstrike_tools", _fake_hexstrike_tools(scenario)):
            agent = await build_agent()
            config: RunnableConfig = {
                "configurable": {"thread_id": str(uuid.uuid4())},
                "recursion_limit": RECURSION_LIMIT,
            }
            payload: RunResult = {"messages": [{"role": "user", "content": scenario.PROMPT}]}

            result: RunResult = await agent.ainvoke(payload, config)
            auto_approve = getattr(scenario, "AUTO_APPROVE", True)

            while result.get("__interrupt__") and auto_approve:
                action_requests = result["__interrupt__"][0].value["action_requests"]
                decisions = [{"type": "approve"} for _ in action_requests]
                resume: Command = Command(resume={"decisions": decisions})
                result = await agent.ainvoke(resume, config)

            return scenario.check(result)
    except Exception as e:  # noqa: BLE001 - one broken scenario (bad key, timeout, ...) shouldn't kill the batch
        return EvalResult(passed=False, reason=f"run failed: {e}")
    finally:
        SCOPE_FILE.unlink(missing_ok=True)


async def _main(names: list[str]) -> None:
    for var in ("GOOGLE_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
        if not os.environ.get(var):
            raise SystemExit(f"{var} not set — evals need real model credentials, see .env.example")

    selected = names or _list_scenarios()
    unknown = set(selected) - set(_list_scenarios())
    if unknown:
        raise SystemExit(f"unknown scenario(s): {', '.join(sorted(unknown))}")

    results: list[tuple[str, EvalResult]] = []
    for name in selected:
        scenario = importlib.import_module(f"evals.scenarios.{name}")
        print(f"running {name}...")
        result = await _run_scenario(scenario)
        results.append((name, result))
        print(f"  {'PASS' if result.passed else 'FAIL'} — {result.reason}")

    failed = [name for name, r in results if not r.passed]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")

    if failed:
        raise SystemExit(f"failed: {', '.join(failed)}")


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1:]))
