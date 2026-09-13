<p align="center">
  <img src="assets/banner.jpeg" alt="fenrir" width="100%">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.13%2B-blue" alt="Python 3.13+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/LLMs-free--tier-orange" alt="Free-tier LLMs">
  <img src="https://img.shields.io/badge/mode-human--in--the--loop-8b5cf6" alt="Human in the loop">
</p>

<h1 align="center">fenrir</h1>

<p align="center">
  <b>A multi-agent, human-in-the-loop assistant for bug bounty and web application penetration testing.</b>
</p>

<p align="center">
  An orchestrator scopes the engagement and delegates to four specialists — recon, web, exploit, and triage —<br>
  each backed by vendored methodology playbooks and a shared belt of 150+ security tools exposed over MCP.
</p>

> **Authorized use only.** fenrir refuses any target not listed in `scope.md`, and every tool call that sends traffic pauses for operator approval. It is not autonomous. Use it only within a bug bounty program's stated scope or an engagement you hold written authorization for. Unauthorized scanning or exploitation may be illegal in your jurisdiction.

## Overview

The orchestrator never touches a target itself: it reads `scope.md`, plans the engagement in phases (recon → surface review → testing → exploitation → reporting), and dispatches work to subagents through a `task` tool. Each subagent runs its own model, sees only the tools relevant to its role, and follows an `Agent Skill` playbook for method. Offensive tool calls and shell execution are registered as human-in-the-loop interrupts — the run halts and waits for an approve/reject decision before proceeding.

## Agents

| Agent | Responsibility | Default model |
|-------|----------------|---------------|
| `orchestrator` | Scope enforcement, planning, delegation. Runs no offensive tools. | `gemini-3.6-flash` |
| `recon` | Subdomain, DNS, port, technology, and content discovery; takeover checks. | `gpt-oss-120b` |
| `web` | Hands-on testing of one surface against OWASP WSTG methodology. | `gemini-3.6-flash` |
| `exploit` | Minimal proof-of-concept for a single confirmed finding. Always gated. | `nemotron-super` |
| `triage` | Deduplication, CVSS scoring, report writing. | `gpt-oss-120b` |

Model routing is a single table (`MODELS`) in [`src/fenrir/config.py`](src/fenrir/config.py).

## Features

- **Five cooperating agents** on [deepagents](https://docs.langchain.com/oss/python/deepagents) — per-agent model, tool belt, and prompt.
- **30 vendored [Anthropic Cybersecurity Skills](https://github.com/anthropics/anthropic-cybersecurity-skills)** as methodology: OWASP WSTG, SQLi, SSRF, IDOR, XXE, request smuggling, cache poisoning, JWT, GraphQL, and more.
- **150+ tools from [HexStrike AI](https://github.com/0x4m4/hexstrike-ai)** over MCP — nmap, nuclei, ffuf, sqlmap, subfinder, katana, dalfox, and the rest.
- **Scope enforcement** — a typed `ScopePolicy` (host, path, and port) backed by `scope.md`; the `in_scope` tool every agent must consult before acting on a host reads from it.
- **Human-in-the-loop** — `execute` and every traffic-sending tool interrupt for approval. Recon and web approval can be relaxed via `.env`; exploit's gate cannot be disabled by any environment variable.
- **Free-tier models only** — Gemini, Groq, and OpenRouter `:free`.
- **Three interfaces** — terminal REPL, streaming HTTP API, and a React (Vite) web UI with persisted conversation history.
- **Graceful degradation** — if the HexStrike server is unreachable, agents fall back to guidance without the tool belt.

## Requirements

- Python 3.13+ and [uv](https://docs.astral.sh/uv/)
- At least one LLM API key: `GOOGLE_API_KEY`, `GROQ_API_KEY`, or `OPENROUTER_API_KEY` (each has a free tier)
- *Optional:* Node.js 18+ for the web UI
- *Optional:* a running [HexStrike](https://github.com/0x4m4/hexstrike-ai) server for the tool belt

## Installation

```bash
git clone https://github.com/DaviAlcanfor/fenrir.git
cd fenrir
uv sync
cp .env.example .env                        # add your LLM key(s)
mkdir -p engagement
cp scope.md.example engagement/scope.md     # define what is in scope
```

Agents see `engagement/` as their entire filesystem (`/`) — `scope.md` and
`findings/` live there and nowhere else. This is deliberate: it's what stops
an agent from reading or writing fenrir's own source tree.

## Usage

### Terminal

```bash
uv run fenrir
```

Opens a REPL. Point it at your `scope.md`, then ask it to run recon, test a surface, or write up findings. Gated tool calls prompt `approve? [y/N]` — anything but an explicit `y`/`yes` rejects.

### HTTP API

```bash
uv run fenrir-api               # http://localhost:8000
```

| Endpoint | Body | Description |
|----------|------|-------------|
| `GET /health` | — | Agent readiness |
| `POST /chat` | `{ message, thread_id? }` | Start or continue a run (SSE) |
| `POST /threads/{id}/resume` | `{ decisions }` | Answer a gated tool call (SSE) |
| `GET /threads` | — | List past conversations |
| `GET /threads/{id}` | — | Replay a conversation's messages |
| `GET /threads/{id}/usage` | — | Token cost per agent (graph node) for that thread |

Streaming responses emit `thread`, `message`, `interrupt`, `error`, and `done` events. Conversations and per-agent token usage persist in `fenrir.db` (SQLite) across restarts.

### Web UI

```bash
uv run fenrir-api                              # terminal 1
cd web
cp .env.local.example .env.local
npm install && npm run dev                     # http://localhost:3000
```

A Vite + React client for the API: conversation sidebar with history and an approval panel for gated tools.

## Configuration

Read from `.env` at startup:

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` / `GROQ_API_KEY` / `OPENROUTER_API_KEY` | — | LLM provider keys |
| `HEXSTRIKE_SERVER` | `http://localhost:8888` | HexStrike API URL |
| `HEXSTRIKE_MCP_PATH` | `../hexstrike-ai/hexstrike_mcp.py` | MCP bridge script |
| `APPROVAL__REQUIRE_APPROVAL_RECON` | `true` | Set `false` to run recon's gated tools unattended (not recommended) |
| `APPROVAL__REQUIRE_APPROVAL_WEB` | `true` | Set `false` to run web's gated tools unattended (not recommended) |

Exploit's approval gate has no equivalent variable — it cannot be disabled from `.env` or anywhere else.

## Project structure

| Path | Contents |
|------|----------|
| `src/fenrir/config.py` | Paths, `Agent` / `Model` enums, and the `MODELS` routing table |
| `src/fenrir/settings.py` | `Settings` — keys, HexStrike location, `ApprovalSettings` |
| `src/fenrir/policy/` | `ScopePolicy` (host/path/port) and `GuardedHttpClient`, the egress guard |
| `src/fenrir/agents/` | `SubAgentSpec`, `make_subagents(tools)`, `build_agent(checkpointer=None)`, prompt loader |
| `src/fenrir/{tools,mcp,cli}.py` | Scope tool, HexStrike belt, REPL |
| `src/fenrir/api/` | FastAPI app — routes, SSE streaming, SQLite conversation history |
| `src/fenrir/prompts/` | One prompt per agent |
| `src/fenrir/skills/` | 30 vendored `SKILL.md` playbooks — junctioned into `engagement/skills` so agents can still reach them from their isolated root |
| `engagement/` | The agents' entire filesystem — `scope.md`, `findings/`. Gitignored; create it yourself (see Installation) |
| `web/` | Vite + React UI, a client of `fenrir-api` |
| `tests/` | `uv run python tests/test_fenrir.py` |
| `evals/` | Behavior evals (real LLM, mocked tool belt) — `uv run python evals/runner.py`, see `evals/README.md` |

[`AGENTS.md`](AGENTS.md) documents the architecture and the rules the agents operate under.

## Dependencies

| Package | Purpose |
|---------|---------|
| `deepagents` | Orchestrator and subagents, skills, filesystem, human-in-the-loop |
| `langchain-mcp-adapters` | HexStrike tools over MCP |
| `langchain-google-genai` · `langchain-groq` · `langchain-openrouter` | LLM providers |
| `langgraph-checkpoint-sqlite` | Conversation persistence |
| `pydantic-settings` | Typed configuration from `.env` |
| `fastapi` · `uvicorn` | Streaming HTTP API |
| `vite` · `react` | Web UI (`web/`) |

## License

MIT — see [LICENSE](LICENSE).
