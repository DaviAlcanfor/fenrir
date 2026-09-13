import { useEffect, useRef, useState } from "react";
import { type AgentInfo, type AgentState } from "./components/AgentStatus";
import { AgentGraph, SPECIALISTS } from "./components/AgentGraph";
import { ApprovalPanel } from "./components/ApprovalPanel";
import { colorFor } from "./lib/agentColor";
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

// Only the 4 real specialists get their own activity feed — everything else
// (orchestrator, and deepagents' internal middleware nodes) stays in the main chat.
const SPECIALIST_SET: ReadonlySet<string> = new Set(SPECIALISTS);

/** `task(...)` calls carry a long free-text description + subagent_type — render
 * those as readable prose with a badge instead of a raw JSON blob. Other tool
 * calls get compact key=value args instead of JSON.stringify's quoted keys. */
function ToolCallView({ tc }: { tc: { name: string; args: Record<string, unknown> } }) {
  if (tc.name === "task" && typeof tc.args.description === "string") {
    return (
      <div className="task-call">
        <span className="task-badge">→ delegating to {String(tc.args.subagent_type ?? "subagent")}</span>
        <p>{tc.args.description}</p>
      </div>
    );
  }

  const argStr = Object.entries(tc.args)
    .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(", ");
  return (
    <pre className="tool-call">
      ⚙ {tc.name}({argStr})
    </pre>
  );
}

function MessageView({
  m,
  i,
  expanded,
  onToggle,
  compact,
}: {
  m: ChatMessage;
  i: number;
  expanded: boolean;
  onToggle: () => void;
  compact?: boolean;
}) {
  const isToolResult = m.type === "tool";
  const preview = (m.content || "").split("\n")[0].slice(0, compact ? 50 : 90);

  return (
    <div
      className={`msg ${m.type}${compact ? " compact" : ""}`}
      style={m.node ? { borderLeftColor: colorFor(m.node), borderLeftWidth: 3 } : undefined}
    >
      {m.type !== "human" && !compact && <div className="role">{m.node ?? m.type}</div>}
      {m.tool_calls?.map((tc, j) => (
        <ToolCallView tc={tc} key={j} />
      ))}
      {isToolResult ? (
        <>
          <button className="tool-toggle" onClick={onToggle}>
            {expanded ? "▾" : "▸"} {preview}
            {(m.content || "").length > preview.length ? "…" : ""}
          </button>
          {expanded && <pre>{m.content}</pre>}
        </>
      ) : (
        m.content && <pre>{m.content}</pre>
      )}
    </div>
  );
}

export default function App() {
  const [threads, setThreads] = useState<ThreadMeta[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [interrupt, setInterrupt] = useState<InterruptRequest | null>(null);
  const [busy, setBusy] = useState(false);
  const [input, setInput] = useState("");
  const [agentStatus, setAgentStatus] = useState<Record<string, AgentInfo>>({});
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const toggleExpanded = (i: number) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });

  const refreshThreads = () => listThreads().then(setThreads);
  useEffect(() => {
    refreshThreads();
  }, []);

  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages, agentStatus, interrupt]);

  const handlers = {
    thread: setThreadId,
    message: (m: ChatMessage) => {
      setMessages((prev) => [...prev, m]);
      if (m.node) {
        const action = m.tool_calls?.[0]?.name ?? "responded";
        setAgentStatus((prev) => ({ ...prev, [m.node as string]: { status: "responded", action } }));
      }
    },
    interrupt: setInterrupt,
    agent_status: ({ node, status }: { node: string; status: AgentState }) =>
      setAgentStatus((prev) => ({ ...prev, [node]: { status, action: prev[node]?.action } })),
    error: (detail: string) => setMessages((prev) => [...prev, { type: "error", content: detail }]),
    done: () => {
      setBusy(false);
      refreshThreads();
      setAgentStatus((prev) => {
        const next = { ...prev };
        for (const node in next) if (next[node].status === "thinking") next[node] = { ...next[node], status: "terminated" };
        return next;
      });
    },
  };

  const drive = async (fn: () => Promise<void>) => {
    setBusy(true);
    setInterrupt(null);
    setAgentStatus({});
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
    setAgentStatus({});
  };

  const open = async (id: string) => {
    if (busy) return;
    setInterrupt(null);
    setThreadId(id);
    setAgentStatus({});
    try {
      setMessages(await getThread(id));
    } catch {
      setMessages([{ type: "error", content: "could not load this conversation" }]);
    }
  };

  // Split the flat message list: the main chat gets everything except the 4
  // specialists' own actions, which feed the activity log under the graph.
  // Indices are kept from the original array so expand/collapse state lines up.
  const indexed = messages.map((m, i) => ({ m, i }));
  const mainMessages = indexed.filter(({ m }) => !SPECIALIST_SET.has(m.node ?? ""));
  const specialistMessages = indexed.filter(({ m }) => SPECIALIST_SET.has(m.node ?? ""));

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
          {mainMessages.map(({ m, i }) => (
            <MessageView m={m} i={i} key={i} expanded={expanded.has(i)} onToggle={() => toggleExpanded(i)} />
          ))}
          {busy && !interrupt && (
            <div className="msg ai typing">
              <span className="dot" />
              <span className="dot" />
              <span className="dot" />
            </div>
          )}
          <div ref={bottomRef} />
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

      <aside className="agent-panels">
        <AgentGraph status={agentStatus} />

        <div className="activity-log">
          <div className="sub">specialist activity</div>
          {specialistMessages.length === 0 && <span className="sub muted">nothing delegated yet</span>}
          {specialistMessages.map(({ m, i }) => (
            <MessageView m={m} i={i} key={i} expanded={expanded.has(i)} onToggle={() => toggleExpanded(i)} compact />
          ))}
        </div>
      </aside>
    </div>
  );
}
