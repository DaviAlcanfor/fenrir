# fenrir — agent guide

Multi-agent **bug bounty / web pentest** assistant. Human stays in the loop: agents
recon, test, and draft findings; a person approves anything that touches the target
offensively.

## Stack

- **[deepagents](https://docs.langchain.com/oss/python/deepagents)** — orchestrator +
  subagents, skills middleware, filesystem, human-in-the-loop. We add almost no
  framework code; `create_deep_agent(...)` does the assembly.
- **[Anthropic-Cybersecurity-Skills](https://github.com/anthropics/...)** — 30 curated
  `SKILL.md` playbooks vendored in [src/skills/](src/skills/). These are *methodology*,
  not code the agent runs.
- **[HexStrike AI](https://github.com/0x4m4/hexstrike-ai)** — 150+ security tools
  exposed over MCP (nmap, nuclei, ffuf, sqlmap, subfinder, katana, dalfox, …).
  Runs as a separate process; fenrir connects as an MCP client.
- **Free LLM providers** — Gemini (free tier), Groq, OpenRouter `:free` models.
  `Agent` / `Model` `StrEnum`s and the `MODELS` routing table live in
  [src/fenrir/config.py](src/fenrir/config.py).

## Layout

```
src/fenrir/
  config.py     paths + Agent/Model StrEnums + MODELS routing table
  settings.py   Settings(BaseSettings): keys, HexStrike URL/path, require_approval
  prompts.py    load(Agent.RECON) -> src/prompts/recon.md   (one-liner)
  tools.py      custom LangChain tools (in_scope) — injected into every agent
  mcp.py        MultiServerMCPClient -> HexStrike tools (async)
  subagents.py  SubAgentSpec TypedDict + make_subagents(tools)
  agents.py     build_agent(checkpointer=None): model + prompt + tools + subagents + backend
  cli.py        main(): REPL with human-in-the-loop interrupts
  server.py     FastAPI (`fenrir-api`): POST /chat + POST /threads/{id}/resume (SSE)
src/prompts/    orchestrator.md, recon.md, web.md, exploit.md, triage.md
src/skills/     30 vendored SKILL.md playbooks (see list below)
web/            Next.js chat UI (GSAP via @gsap/react), talks to fenrir-api over SSE
```

Both `cli.py` and `server.py` build the agent with an `InMemorySaver` for
per-thread state. SSE events: `thread`, `message`, `interrupt`, `error`, `done`.

## Agents

| Agent | Job | Tools | Runs offensive tools? |
|---|---|---|---|
| **orchestrator** (main) | Scope, plan, delegate, enforce `scope.md`. | filesystem, `task` | No |
| **recon** | Subdomain/DNS/port/tech/content discovery, link-takeover checks. | HexStrike passive+active recon | Passive auto; active needs approval |
| **web** | WSTG methodology, targeted testing of a surface. | HexStrike web tools + `execute` | Yes — gated |
| **exploit** | Minimal PoC for one *confirmed* finding. | HexStrike + `execute` | Yes — always gated |
| **triage** | Dedupe, CVSS, write report in the skill's output format. | filesystem | No |

Model routing (`MODELS` in `config.py` — edit the table to change it):

- orchestrator, web → `google_genai:gemini-2.0-flash`
- recon, triage → `groq:llama-3.3-70b-versatile`
- exploit → `openrouter:deepseek/deepseek-r1:free`

## Rules for agents working in this repo

1. **Scope is law.** Every engagement has a `scope.md` (in-scope hosts/paths, explicit
   out-of-scope, rate limits). Refuse any target not listed. The orchestrator checks
   this before delegating.
2. **Not autonomous.** `execute` and every HexStrike tool that sends traffic to the
   target are registered in `interrupt_on` — they pause for human approval. Do not
   remove those gates.
3. **No DoS, no destructive payloads, no lateral movement, no data exfiltration.**
   PoC = the minimum to demonstrate impact (one record, one callback, `id` output).
4. **Skills are read-only guidance.** Follow the `SKILL.md` workflow; do not modify
   vendored skills.
5. **Report format** follows `performing-web-application-vulnerability-triage` and the
   `## Finding:` block in `performing-web-application-penetration-test`.

## Running

```bash
# 1. start HexStrike server (separate terminal, its own venv)
python ../hexstrike-ai/hexstrike_server.py         # Flask on :8888

# 2. configure
cp .env.example .env    # add GROQ_API_KEY / GOOGLE_API_KEY / OPENROUTER_API_KEY

# 3. run it — pick one
uv run fenrir        # terminal REPL
uv run fenrir-api    # HTTP API on :8000 (the web/ UI is a client of this)
```

If HexStrike is unreachable, fenrir still starts — subagents just lose their tool
belt and fall back to guidance-only.

## Vendored skills (30)

recon: `conducting-external-reconnaissance-with-osint`,
`performing-subdomain-enumeration-with-subfinder`,
`performing-dns-enumeration-and-zone-transfer`, `exploiting-broken-link-hijacking`

web core: `performing-web-application-penetration-test`,
`performing-web-application-vulnerability-triage`, `testing-for-xss-vulnerabilities`,
`exploiting-sql-injection-vulnerabilities`, `exploiting-sql-injection-with-sqlmap`,
`exploiting-nosql-injection-vulnerabilities`, `exploiting-server-side-request-forgery`,
`performing-blind-ssrf-exploitation`, `exploiting-template-injection-vulnerabilities`,
`testing-for-xxe-injection-vulnerabilities`, `exploiting-insecure-deserialization`,
`exploiting-idor-vulnerabilities`, `exploiting-http-request-smuggling`,
`performing-directory-traversal-testing`

web extended: `testing-cors-misconfiguration`,
`testing-for-open-redirect-vulnerabilities`, `testing-for-host-header-injection`,
`performing-web-cache-poisoning-attack`, `performing-web-cache-deception-attack`,
`exploiting-prototype-pollution-in-javascript`,
`exploiting-race-condition-vulnerabilities`,
`performing-web-application-firewall-bypass`

auth / api: `testing-for-json-web-token-vulnerabilities`,
`testing-for-broken-access-control`, `conducting-api-security-testing`,
`performing-graphql-security-assessment`
