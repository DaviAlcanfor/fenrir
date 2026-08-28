# fenrir

Multi-agent, **human-in-the-loop** assistant for bug bounty / web pentesting.

Five agents built on [deepagents](https://docs.langchain.com/oss/python/deepagents):
an **orchestrator** that scopes and delegates, plus **recon**, **web**, **exploit**,
and **triage** specialists. Methodology comes from 30 vendored
[Anthropic Cybersecurity Skills](https://github.com/anthropics/anthropic-cybersecurity-skills);
the tool belt (nmap, nuclei, ffuf, sqlmap, subfinder, katana, dalfox, …) comes from
[HexStrike AI](https://github.com/0x4m4/hexstrike-ai) over MCP. LLMs are free-tier
(Gemini / Groq / OpenRouter).

Every offensive tool call pauses for your approval. It is **not** autonomous.

See [AGENTS.md](AGENTS.md) for the architecture and the rules the agents follow.

## Quickstart

```sh
uv sync
cp .env.example .env            # add GOOGLE_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY
cp scope.md.example scope.md    # define what is in scope — fenrir refuses everything else

# optional: start the HexStrike tool server in its own venv/terminal
python ../hexstrike-ai/hexstrike_server.py     # Flask on :8888

uv run fenrir
```

Without HexStrike reachable, fenrir still runs — subagents just fall back to
guidance-only.

## API + Web UI

`fenrir-api` is a thin FastAPI over the agent — two SSE endpoints (`POST /chat`,
`POST /threads/{id}/resume`) plus `GET /health`. The Next.js UI in [web/](web/)
(GSAP animations) is a client for it.

```sh
uv run fenrir-api                 # http://localhost:8000

cd web && cp .env.local.example .env.local && npm install && npm run dev
```

See [src/fenrir/server.py](src/fenrir/server.py) and [web/README.md](web/README.md).

## Layout

| Path | What |
|---|---|
| `src/fenrir/config.py` | paths + `Agent`/`Model` enums + `MODELS` routing table |
| `src/fenrir/settings.py` | `Settings(BaseSettings)` — keys, HexStrike URL/path, `require_approval` |
| `src/fenrir/subagents.py` | `SubAgentSpec` + `make_subagents(tools)` |
| `src/fenrir/{tools,mcp,agents,cli}.py` | custom tools, HexStrike belt, assembly, REPL |
| `src/fenrir/server.py` | FastAPI (`fenrir-api`) — streaming chat + resume |
| `src/prompts/` | one `.md` per agent |
| `src/skills/` | 30 vendored `SKILL.md` playbooks |
| `web/` | Next.js chat UI (GSAP), client of `fenrir-api` |
| `tests/test_fenrir.py` | `uv run python tests/test_fenrir.py` |

## Notes

- Repo sits under OneDrive; `pyproject.toml` sets `link-mode = "copy"` so `uv` doesn't
  choke on hardlinks.
- To change which model an agent uses, edit the `MODELS` table in `config.py`.
- `REQUIRE_APPROVAL=false` disables approval gating. Don't.
