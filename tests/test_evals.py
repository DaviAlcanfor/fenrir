"""Runnable self-checks for the evals runner's own logic — no LLM calls, no
API key needed. The scenarios themselves (evals/scenarios/*.py) are only
exercised by `python evals/runner.py`, not here — that costs real API calls.

`uv run python tests/test_evals.py`
"""

import asyncio
import importlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evals.runner import SCOPE_FILE, _list_scenarios, _run_scenario  # noqa: E402


def test_lists_every_scenario_module():
    assert set(_list_scenarios()) == {
        "refuses_out_of_scope",
        "requires_approval_before_gated_tool",
        "synthesizes_a_planted_finding",
    }


def test_every_scenario_has_the_required_shape():
    for name in _list_scenarios():
        scenario = importlib.import_module(f"evals.scenarios.{name}")
        assert isinstance(scenario.SCOPE_MD, str) and scenario.SCOPE_MD.strip()
        assert isinstance(scenario.PROMPT, str) and scenario.PROMPT.strip()
        assert callable(scenario.check)


def test_refuses_to_run_over_a_real_scope_md():
    async def run() -> None:
        assert not SCOPE_FILE.exists(), f"a real scope.md exists at {SCOPE_FILE} — refusing to test over it"

        SCOPE_FILE.write_text("# a real engagement's scope\n", encoding="utf-8")
        try:
            scenario = importlib.import_module("evals.scenarios.refuses_out_of_scope")
            try:
                await _run_scenario(scenario)
                raise AssertionError("expected RuntimeError")
            except RuntimeError as e:
                assert "refusing to overwrite" in str(e)
        finally:
            SCOPE_FILE.unlink(missing_ok=True)

    asyncio.run(run())


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all passed")
