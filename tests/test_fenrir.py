"""Runnable self-checks for the wiring logic. `uv run python tests/test_fenrir.py`."""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fenrir import prompts, subagents as sa  # noqa: E402
from fenrir.config import MODELS, Agent, Model  # noqa: E402
from fenrir.subagents import _belt, _gate  # noqa: E402
from fenrir.tools import _matches, in_scope, load_paths, load_scope  # noqa: E402

FAKE = [SimpleNamespace(name=n) for n in ("subfinder_scan", "sqlmap_scan", "nmap_scan", "metasploit_exploit")]


def test_belt_filters_by_agent():
    assert {t.name for t in _belt(FAKE, Agent.RECON)} == {"subfinder_scan", "nmap_scan"}  # no sqlmap/metasploit
    assert {t.name for t in _belt(FAKE, Agent.WEB)} == {"sqlmap_scan"}
    assert _belt(FAKE, Agent.EXPLOIT) == FAKE  # None = whole belt


def test_gate_wraps_tools_plus_execute():
    g = _gate(Agent.WEB, FAKE)
    assert g["execute"] is True
    assert all(g[t.name] is True for t in FAKE)


def test_gate_empty_when_agent_approval_disabled():
    old = sa.settings.approval.require_approval_web
    sa.settings.approval.require_approval_web = False
    try:
        assert _gate(Agent.WEB, FAKE) == {}
    finally:
        sa.settings.approval.require_approval_web = old


def test_exploit_gate_cannot_be_disabled():
    old_recon = sa.settings.approval.require_approval_recon
    old_web = sa.settings.approval.require_approval_web
    sa.settings.approval.require_approval_recon = False
    sa.settings.approval.require_approval_web = False
    try:
        g = _gate(Agent.EXPLOIT, FAKE)
        assert g["execute"] is True
        assert all(g[t.name] is True for t in FAKE)
    finally:
        sa.settings.approval.require_approval_recon = old_recon
        sa.settings.approval.require_approval_web = old_web


def test_exploit_gate_ignores_env_override():
    import os

    os.environ["APPROVAL__REQUIRE_APPROVAL_EXPLOIT"] = "false"
    try:
        from fenrir.settings import ApprovalSettings

        assert ApprovalSettings().require_approval_exploit is True
    finally:
        del os.environ["APPROVAL__REQUIRE_APPROVAL_EXPLOIT"]


def test_models_cover_every_agent():
    assert set(MODELS) == set(Agent)
    assert all(isinstance(m, Model) for m in MODELS.values())


def test_prompts_load_every_agent():
    for agent in Agent:
        assert len(prompts.load(agent)) > 200


def test_root_shell_requires_approval():
    from fenrir.agents import ROOT_INTERRUPT_ON

    assert ROOT_INTERRUPT_ON.get("execute") is True


def test_general_purpose_subagent_is_locked_down():
    specs = sa.make_subagents(FAKE)
    gp = next(s for s in specs if s["name"] == "general-purpose")
    assert gp["tools"] == []
    assert gp["interrupt_on"].get("execute") is True


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


def test_load_paths_extracts_paths_line():
    p = Path(__file__).parent / "_scope_paths_fixture.md"
    p.write_text(
        "# scope\n## In scope\n- *.example.com\n- Paths: /api/*, /app/*\n",
        encoding="utf-8",
    )
    try:
        assert load_paths(p) == ("/api/*", "/app/*")
    finally:
        p.unlink()


def test_load_paths_defaults_to_wildcard_when_absent():
    p = Path(__file__).parent / "_scope_nopaths_fixture.md"
    p.write_text("# scope\n## In scope\n- *.example.com\n", encoding="utf-8")
    try:
        assert load_paths(p) == ("*",)
    finally:
        p.unlink()


def test_in_scope_tool_respects_path_restriction():
    p = Path(__file__).parent.parent / "scope.md"
    assert not p.exists(), "a real scope.md exists — refusing to overwrite it for a test"
    p.write_text(
        "# scope\n## In scope\n- *.example.com\n- Paths: /api/*\n",
        encoding="utf-8",
    )
    try:
        assert "IN SCOPE" in in_scope.invoke({"target": "https://app.example.com/api/users"})
        assert "OUT OF SCOPE" in in_scope.invoke({"target": "https://app.example.com/admin"})
    finally:
        p.unlink()


def test_cli_approval_is_fail_closed():
    from fenrir.cli import _approved

    assert _approved("y")
    assert _approved("Y")
    assert _approved("yes")
    assert _approved("  yes  ")
    assert not _approved("")  # empty Enter must NOT approve
    assert not _approved("n")
    assert not _approved("sure")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all passed")
