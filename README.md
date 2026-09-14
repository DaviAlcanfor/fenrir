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

Model routing is a single table (`MODELS`) in [`src/fenrir/config.py`](src/fenrir/config.py) — each agent gets an ordered chain of models, not just one. If the first errors (rate limits, outages), `FallbackChatModel` retries the next one automatically.

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
- *Optional:* [ripgrep](https://github.com/BurntSushi/ripgrep) on `PATH` — the filesystem tools fall back to a slower Python search without it, and lose automatic `.gitignore` handling (agents end up walking `.venv/`, `.git/`, etc.)

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

Streaming responses emit `thread`, `message`, `interrupt`, `error`, and `done` events. Conversations and per-agent token usage persist in `data/fenrir.db` (SQLite) across restarts.

### Web UI

```bash
uv run fenrir-api                              # terminal 1
cd web
cp .env.local.example .env.local
npm install && npm run dev                     # http://localhost:3000
```

A Vite + React client for the API: conversation sidebar with history and an approval panel for gated tools.

### HexStrike on Windows — Docker or WSL

HexStrike's tool belt (nmap, subfinder, nuclei, sqlmap, ffuf, ...) is close to
100% Linux-only tooling, and its own Python dependencies don't fare much
better natively on Windows: `mitmproxy` pulls in a WinDivert driver that
Windows Defender / most antivirus flags as a dual-use `RiskTool` and blocks
the download outright (it's a legitimate but genuinely powerful
packet-capture driver — the same category nmap/hydra/mimikatz fall into, not
malware). If you're on Windows, run HexStrike either in **Docker** (no WSL
setup needed) or inside **WSL2**.

#### Docker (recommended — no WSL needed)

Requires Docker Desktop and a sibling checkout of `hexstrike-ai` (same
assumption as the WSL/native scripts below):

```powershell
docker compose up --build -d hexstrike   # builds docker/hexstrike.Dockerfile, serves :8888
```

`scripts/start-dev-docker.ps1` does this and then launches `fenrir-api` and
the web UI in their own windows, same as `scripts/start-dev.ps1` but without
WSL. The image installs the same tool subset `scripts/check_tools.sh` checks
for (not the full 150+ HexStrike supports) — see
`docker/hexstrike.Dockerfile` to add more.

#### WSL2

```powershell
wsl --install -d kali-linux        # once — installs Kali as a WSL2 distro
```

Inside that WSL distro:

```bash
python3 -m venv ~/hexstrike-env
~/hexstrike-env/bin/pip install -r /mnt/c/path/to/hexstrike-ai/requirements.txt
# install the CLI tools the belt actually calls — apt has most of them:
sudo apt-get install -y nmap sqlmap gobuster ffuf nikto dnsenum masscan whatweb wafw00f amass \
                        golang-go feroxbuster dirsearch wpscan pipx
# ProjectDiscovery's Go tools aren't packaged — build them:
GOBIN=/usr/local/bin go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
GOBIN=/usr/local/bin go install github.com/projectdiscovery/httpx/cmd/httpx@latest
GOBIN=/usr/local/bin go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
GOBIN=/usr/local/bin go install github.com/projectdiscovery/katana/cmd/katana@latest
GOBIN=/usr/local/bin go install github.com/projectdiscovery/naabu/v2/cmd/naabu@latest
GOBIN=/usr/local/bin go install github.com/hahwul/dalfox/v2@latest
pipx install arjun
pipx ensurepath                    # then export PATH="$PATH:/root/.local/bin" for non-login shells
```

Then start it from WSL, pointed at the Windows-side checkout via `/mnt/c/...`:

```bash
~/hexstrike-env/bin/python /mnt/c/path/to/hexstrike-ai/hexstrike_server.py
```

`fenrir-api` still runs natively on Windows and reaches it at
`http://localhost:8888` — WSL2 forwards `localhost` both ways in the default
configuration, no extra networking setup needed.

`scripts/start-dev.ps1` launches HexStrike (via WSL), `fenrir-api`, and the
web UI each in their own PowerShell window in one shot — adjust the
hexstrike-ai path in it if your checkout isn't a sibling of this repo.

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
| `src/fenrir/agents/` | `SubAgentSpec`, `make_subagents(tools)`, `build_agent(checkpointer=None)`, prompt loader, `FallbackChatModel` |
| `src/fenrir/{tools,mcp,cli}.py` | Scope tool, HexStrike belt, REPL |
| `src/fenrir/api/` | FastAPI app — routes, SSE streaming, SQLite conversation history |
| `src/fenrir/prompts/` | One prompt per agent |
| `src/fenrir/skills/` | 30 vendored `SKILL.md` playbooks — junctioned into `engagement/skills` so agents can still reach them from their isolated root |
| `engagement/` | The agents' entire filesystem — `scope.md`, `findings/`. Gitignored; create it yourself (see Installation) |
| `data/` | `fenrir.db` (SQLite) — conversation history + token usage. Gitignored, created on first run |
| `web/` | Vite + React UI, a client of `fenrir-api` |
| `tests/` | `uv run python tests/test_fenrir.py` |
| `evals/` | Behavior evals (real LLM, mocked tool belt) — `uv run python evals/runner.py`, see `evals/README.md` |
| `scripts/` | Dev launchers (`start-dev.ps1` WSL, `start-dev-docker.ps1` Docker) and HexStrike/WSL setup helpers |
| `docker/`, `docker-compose.yml` | HexStrike-in-a-container, as a WSL alternative on Windows |

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
