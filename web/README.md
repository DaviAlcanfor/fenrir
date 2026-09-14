# fenrir web

Minimal Vite + React chat UI for fenrir. Talks to the fenrir API (`fenrir-api`)
over server-sent events — no LangGraph SDK, no animation library.

## Run

```sh
# 1. API, from the repo root
cd ..
uv run fenrir-api                 # http://localhost:8000

# 2. this app
cp .env.local.example .env.local
npm install
npm run dev                       # http://localhost:3000
```

## Layout

```text
src/
  main.tsx               entry point
  App.tsx                sidebar (conversation list + "new conversation"),
                          chat log, composer
  index.css               styles, incl. the CSS-only entrance animations
  lib/api.ts              sendMessage() / resume() (SSE), listThreads() / getThread() (JSON)
  components/
    ApprovalPanel.tsx     approve/reject the gated tool calls fenrir pauses
                          on; posts back to /threads/{id}/resume
```

Conversations persist server-side in `data/fenrir.db`; the sidebar is backed by
`GET /threads`. Not included: auth, markdown rendering, token-level streaming.
