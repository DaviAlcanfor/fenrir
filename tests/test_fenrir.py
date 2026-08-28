"""Runnable self-checks for the wiring logic. `uv run python tests/test_fenrir.py`."""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fenrir import prompts, subagents as sa  # noqa: E402
from fenrir.config import MODELS, Agent, Model  # noqa: E402
from fenrir.subagents import _belt, _gate  # noqa: E402
from fenrir.tools import _matches, in_scope, load_scope  # noqa: E402

FAKE = [SimpleNamespace(name=n) for n in ("subfinder_scan", "sqlmap_scan", "nmap_scan", "metasploit_exploit")]


def test_belt_filters_by_agent():
    assert {t.name for t in _belt(FAKE, Agent.RECON)} == {"subfinder_scan", "nmap_scan"}  # no sqlmap/metasploit
    assert {t.name for t in _belt(FAKE, Agent.WEB)} == {"sqlmap_scan"}
    assert _belt(FAKE, Agent.EXPLOIT) == FAKE  # None = whole belt


def test_gate_wraps_tools_plus_execute():
    g = _gate(FAKE)
    assert g["execute"] is True
    assert all(g[t.name] is True for t in FAKE)


def test_gate_empty_when_approval_disabled():
    old = sa.settings.require_approval
    sa.settings.require_approval = False
    try:
        assert _gate(FAKE) == {}
    finally:
        sa.settings.require_approval = old


def test_models_cover_every_agent():
    assert set(MODELS) == set(Agent)
    assert all(isinstance(m, Model) for m in MODELS.values())


def test_prompts_load_every_agent():
    for agent in Agent:
        assert len(prompts.load(agent)) > 200


def test_scope_matching():
    assert _matches("app.example.com", "*.example.com")
    assert _matches("example.com", "*.example.com")
    assert not _matches("notexample.com", "*.example.com")
    assert _matches("203.0.113.5", "203.0.113.0/24")
    assert not _matches("203.0.114.5", "203.0.113.0/24")


def test_scope_parse_and_classify():
    p = Path(__file__).parent / "_scope_fixture.md"
    p.write_text(
        "# scope\n## In scope\n- *.example.com\n- 203.0.113.0/24\n"
        "## Out of scope\n- blog.example.com\n",
        encoding="utf-8",
    )
    try:
        allow, deny = load_scope(p)
        assert "*.example.com" in allow and "blog.example.com" in deny
        # in_scope() reads the real scope.md, so just exercise the parser+matcher here
        assert _matches("blog.example.com", deny[0])
    finally:
        p.unlink()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all passed")
