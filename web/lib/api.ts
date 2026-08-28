const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ChatMessage = {
  type: string;
  node?: string | null;
  content: string;
  tool_calls?: { name: string; args: Record<string, unknown> }[];
};

export type ThreadMeta = { thread_id: string; title: string; created_at: string };

export type InterruptRequest = {
  action_requests: { name: string; args: Record<string, unknown>; description?: string }[];
};

export type Decision = { type: "approve" } | { type: "reject"; message?: string };

type Events = {
  thread?: (id: string) => void;
  message?: (m: ChatMessage) => void;
  interrupt?: (r: InterruptRequest) => void;
  error?: (detail: string) => void;
  done?: () => void;
};

/** POST a JSON body and dispatch the server-sent events until `done`. */
async function stream(path: string, body: unknown, on: Events, signal?: AbortSignal) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`API ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const event = /^event: (.*)$/m.exec(frame)?.[1] ?? "message";
      const data = JSON.parse(/^data: ([\s\S]*)$/m.exec(frame)?.[1] ?? "{}");
      if (event === "thread") on.thread?.(data.thread_id);
      else if (event === "message") on.message?.(data as ChatMessage);
      else if (event === "interrupt") on.interrupt?.(data as InterruptRequest);
      else if (event === "error") on.error?.(data.detail);
      else if (event === "done") on.done?.();
    }
  }
}

export const sendMessage = (message: string, threadId: string | null, on: Events, signal?: AbortSignal) =>
  stream("/chat", { message, thread_id: threadId }, on, signal);

export const resume = (threadId: string, decisions: Decision[], on: Events, signal?: AbortSignal) =>
  stream(`/threads/${threadId}/resume`, { decisions }, on, signal);

export async function listThreads(): Promise<ThreadMeta[]> {
  try {
    const r = await fetch(`${API}/threads`);
    return r.ok ? r.json() : [];
  } catch {
    return [];
  }
}

export async function getThread(id: string): Promise<ChatMessage[]> {
  const r = await fetch(`${API}/threads/${id}`);
  if (!r.ok) throw new Error(`API ${r.status}`);
  return (await r.json()).messages;
}
