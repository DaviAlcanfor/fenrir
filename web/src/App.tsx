import { useEffect, useState } from "react";
import { ApprovalPanel } from "./components/ApprovalPanel";
import {
  getThread,
  listThreads,
  resume,
  sendMessage,
  type ChatMessage,
  type Decision,
  type InterruptRequest,
  type ThreadMeta,
} from "./lib/api";

export default function App() {
  const [threads, setThreads] = useState<ThreadMeta[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [interrupt, setInterrupt] = useState<InterruptRequest | null>(null);
  const [busy, setBusy] = useState(false);
  const [input, setInput] = useState("");

  const refreshThreads = () => listThreads().then(setThreads);
  useEffect(() => {
    refreshThreads();
  }, []);

  const handlers = {
    thread: setThreadId,
    message: (m: ChatMessage) => setMessages((prev) => [...prev, m]),
    interrupt: setInterrupt,
    error: (detail: string) => setMessages((prev) => [...prev, { type: "error", content: detail }]),
    done: () => {
      setBusy(false);
      refreshThreads();
    },
  };

  const drive = async (fn: () => Promise<void>) => {
    setBusy(true);
    setInterrupt(null);
    try {
      await fn();
    } catch (e) {
      setMessages((prev) => [...prev, { type: "error", content: String(e) }]);
      setBusy(false);
    }
  };

  const send = (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setMessages((prev) => [...prev, { type: "human", content: text }]);
    setInput("");
    drive(() => sendMessage(text, threadId, handlers));
  };

  const decide = (decisions: Decision[]) => {
    if (threadId) drive(() => resume(threadId, decisions, handlers));
  };

  const newChat = () => {
    setMessages([]);
    setThreadId(null);
    setInterrupt(null);
  };

  const open = async (id: string) => {
    if (busy) return;
    setInterrupt(null);
    setThreadId(id);
    try {
      setMessages(await getThread(id));
    } catch {
      setMessages([{ type: "error", content: "could not load this conversation" }]);
    }
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <button className="new-chat" onClick={newChat}>
          + new conversation
        </button>
        <div className="thread-list">
          {threads.map((t) => (
            <button
              key={t.thread_id}
              className={`thread-item ${t.thread_id === threadId ? "active" : ""}`}
              onClick={() => open(t.thread_id)}
              title={new Date(t.created_at).toLocaleString()}
            >
              {t.title}
            </button>
          ))}
        </div>
      </aside>

      <main>
        <div className="masthead">
          <h1>fenrir</h1>
          <span className="sub">bug bounty assistant · human in the loop</span>
        </div>

        <div className="log">
          {messages.map((m, i) => (
            <div className={`msg ${m.type}`} key={i}>
              <div className="role">{m.node ?? m.type}</div>
              {m.tool_calls?.map((tc, j) => (
                <pre className="tool-call" key={j}>
                  ⚙ {tc.name}({JSON.stringify(tc.args)})
                </pre>
              ))}
              {m.content && <pre>{m.content}</pre>}
            </div>
          ))}
        </div>

        {interrupt ? (
          <ApprovalPanel request={interrupt} disabled={busy} onResume={decide} />
        ) : (
          <div className="composer">
            <form onSubmit={send}>
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="ask fenrir — start by pointing it at a scope.md"
                disabled={busy}
              />
              <button type="submit" disabled={busy}>
                {busy ? "…" : "send"}
              </button>
            </form>
          </div>
        )}
      </main>
    </div>
  );
}
