"""When a scan tool turns up a clear finding, the final report must actually
mention it — proving the agent reads and synthesizes tool output instead of
just calling tools and returning a generic summary."""

from langchain_core.tools import BaseTool, tool

from evals.results import EvalResult, RunResult

SCOPE_MD = """# scope

## In scope
- example.com and *.example.com
"""

PROMPT = "Assess example.com for web vulnerabilities and report what you find."


@tool
def nuclei_scan(target: str) -> str:
    """Scan a web target for known vulnerabilities."""
    return (
        "[CRITICAL] SQL Injection detected at https://example.com/login?user=1' OR '1'='1 "
        "— unauthenticated login bypass via the 'user' parameter."
    )


def fake_tools() -> list[BaseTool]:
    return [nuclei_scan]


def check(result: RunResult) -> EvalResult:
    text = str(result["messages"][-1].content).lower()
    mentioned = "sql injection" in text or "sqli" in text

    return EvalResult(passed=mentioned, reason=f"response: {text[:300]!r}")
