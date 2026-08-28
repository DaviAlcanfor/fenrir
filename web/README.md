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

- `lib/api.ts` — `sendMessage()` / `resume()` (SSE), `listThreads()` / `getThread()` (JSON).
- `app/page.tsx` — sidebar (conversation list + "new conversation"), chat log,
  composer. GSAP entrance on the masthead, sidebar items, and each new message.
- `components/ApprovalPanel.tsx` — approve/reject the gated tool calls fenrir
  pauses on; posts back to `/threads/{id}/resume`.

Conversations persist server-side in `fenrir.db`; the sidebar is backed by
`GET /threads`. Not included: auth, markdown rendering, token-level streaming.
