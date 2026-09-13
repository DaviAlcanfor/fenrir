import { colorFor } from "../lib/agentColor";
import type { AgentInfo } from "./AgentStatus";

export const SPECIALISTS = ["recon", "web", "exploit", "triage"] as const;
const ORCHESTRATOR_KEYS = ["model", "orchestrator"]; // deepagents' root node is literally called "model"

function Bubble({ label, info }: { label: string; info?: AgentInfo }) {
  const active = !!info;
  const color = active ? colorFor(label) : "#3a4149";
  const state = info?.status ?? "idle";

  return (
    <div className={`agent-bubble ${state}`} style={{ borderColor: color }}>
      <span className="bubble-name" style={{ color }}>
        {label}
      </span>
      <span className="bubble-state">{state}</span>
      {info?.action && <span className="bubble-action">{info.action}</span>}
    </div>
  );
}

/** Fixed roster of the 5 roles fenrir always has — orchestrator on top, the four
 * specialists branching off it — lit up live as `status` fills in from SSE events. */
export function AgentGraph({ status }: { status: Record<string, AgentInfo> }) {
  const root = ORCHESTRATOR_KEYS.map((k) => status[k]).find(Boolean);

  return (
    <div className="graph">
      <Bubble label="orchestrator" info={root} />
      <div className="graph-trunk">
        {SPECIALISTS.map((s) => (
          <div className="graph-node" key={s}>
            <Bubble label={s} info={status[s]} />
          </div>
        ))}
      </div>
    </div>
  );
}
