# fenrir web

Minimal Next.js chat UI for fenrir. Talks to the fenrir API (`fenrir-api`) over
server-sent events — no LangGraph SDK. Animations are GSAP via `@gsap/react`
(`useGSAP`, so cleanup and SSR are handled).

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

## Files

- `lib/api.ts` — `sendMessage()` / `resume()`; parses the SSE frames
  (`thread` / `message` / `interrupt` / `error` / `done`).
- `app/page.tsx` — chat log + composer, GSAP entrance on the masthead and on each
  new message.
- `components/ApprovalPanel.tsx` — approve/reject the gated tool calls fenrir
  pauses on; posts back to `/threads/{id}/resume`.

Not included: auth, thread history, markdown rendering, token-level streaming.
