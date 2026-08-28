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
| `orchestrator` | Scope enforcement, planning, delegation. Runs no offensive tools. | `gemini-2.0-flash` |
| `recon` | Subdomain, DNS, port, technology, and content discovery; takeover checks. | `llama-3.3-70b` |
| `web` | Hands-on testing of one surface against OWASP WSTG methodology. | `gemini-2.0-flash` |
| `exploit` | Minimal proof-of-concept for a single confirmed finding. Always gated. | `deepseek-r1` |
| `triage` | Deduplication, CVSS scoring, report writing. | `llama-3.3-70b` |

Model routing is a single table (`MODELS`) in [`src/fenrir/config.py`](src/fenrir/config.py).

## Features

- **Five cooperating agents** on [deepagents](https://docs.langchain.com/oss/python/deepagents) — per-agent model, tool belt, and prompt.
- **30 vendored [Anthropic Cybersecurity Skills](https://github.com/anthropics/anthropic-cybersecurity-skills)** as methodology: OWASP WSTG, SQLi, SSRF, IDOR, XXE, request smuggling, cache poisoning, JWT, GraphQL, and more.
- **150+ tools from [HexStrike AI](https://github.com/0x4m4/hexstrike-ai)** over MCP — nmap, nuclei, ffuf, sqlmap, subfinder, katana, dalfox, and the rest.
- **Scope enforcement** — an `in_scope` tool backed by `scope.md` that every agent must consult before acting on a host.
- **Human-in-the-loop** — `execute` and every traffic-sending tool interrupt for approval; disable only via an explicit environment flag.
- **Free-tier models only** — Gemini, Groq, and OpenRouter `:free`.
- **Three interfaces** — terminal REPL, streaming HTTP API, and a Next.js web UI with persisted conversation history.
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
cp .env.example .env            # add your LLM key(s)
cp scope.md.example scope.md    # define what is in scope
```

## Usage

### Terminal

```bash
uv run fenrir
```

Opens a REPL. Point it at your `scope.md`, then ask it to run recon, test a surface, or write up findings. Gated tool calls prompt `approve? [Y/n]`.

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

Streaming responses emit `thread`, `message`, `interrupt`, `error`, and `done` events. Conversations persist in `fenrir.db` (SQLite) across restarts.

### Web UI

```bash
uv run fenrir-api                              # terminal 1
cd web
cp .env.local.example .env.local
npm install && npm run dev                     # http://localhost:3000
```

A Next.js client for the API: conversation sidebar with history, an approval panel for gated tools, and GSAP transitions.

## Configuration

Read from `.env` at startup:

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` / `GROQ_API_KEY` / `OPENROUTER_API_KEY` | — | LLM provider keys |
| `HEXSTRIKE_SERVER` | `http://localhost:8888` | HexStrike API URL |
| `HEXSTRIKE_MCP_PATH` | `../hexstrike-ai/hexstrike_mcp.py` | MCP bridge script |
| `REQUIRE_APPROVAL` | `true` | Set `false` to run gated tools unattended (not recommended) |

## Project structure

| Path | Contents |
|------|----------|
| `src/fenrir/config.py` | Paths, `Agent` / `Model` enums, and the `MODELS` routing table |
| `src/fenrir/settings.py` | `Settings` — keys, HexStrike location, `require_approval` |
| `src/fenrir/subagents.py` | `SubAgentSpec` and `make_subagents(tools)` |
| `src/fenrir/{tools,mcp,agents,cli,server}.py` | Scope tool, HexStrike belt, assembly, REPL, API |
| `src/prompts/` | One prompt per agent |
| `src/skills/` | 30 vendored `SKILL.md` playbooks |
| `web/` | Next.js UI, a client of `fenrir-api` |
| `tests/` | `uv run python tests/test_fenrir.py` |

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
| `next` · `react` · `gsap` | Web UI (`web/`) |

## License

MIT — see [LICENSE](LICENSE).
