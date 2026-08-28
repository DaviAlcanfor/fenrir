"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { useRef, useState } from "react";
import { ApprovalPanel } from "@/components/ApprovalPanel";
import { resume, sendMessage, type ChatMessage, type Decision, type InterruptRequest } from "@/lib/api";

gsap.registerPlugin(useGSAP);

export default function Page() {
  const root = useRef<HTMLElement>(null);
  const log = useRef<HTMLDivElement>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [interrupt, setInterrupt] = useState<InterruptRequest | null>(null);
  const [busy, setBusy] = useState(false);
  const [input, setInput] = useState("");

  useGSAP(
    () => {
      gsap.from(".masthead", { autoAlpha: 0, y: -16, duration: 0.5, ease: "power2.out" });
    },
    { scope: root },
  );

  // animate whichever message just landed
  useGSAP(
    () => {
      const nodes = log.current?.querySelectorAll(".msg");
      if (nodes?.length) gsap.from(nodes[nodes.length - 1], { autoAlpha: 0, y: 12, duration: 0.3, ease: "power2.out" });
    },
    { scope: log, dependencies: [messages.length] },
  );

  const handlers = {
    thread: setThreadId,
    message: (m: ChatMessage) => setMessages((prev) => [...prev, m]),
    interrupt: setInterrupt,
    error: (detail: string) => setMessages((prev) => [...prev, { type: "error", content: detail }]),
    done: () => setBusy(false),
  };

  const run = async (fn: () => Promise<void>) => {
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
    run(() => sendMessage(text, threadId, handlers));
  };

  const decide = (decisions: Decision[]) => {
    if (!threadId) return;
    run(() => resume(threadId, decisions, handlers));
  };

  return (
    <main ref={root}>
      <div className="masthead">
        <h1>fenrir</h1>
        <span className="sub">bug bounty assistant · human in the loop</span>
      </div>

      <div className="log" ref={log}>
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
  );
}
