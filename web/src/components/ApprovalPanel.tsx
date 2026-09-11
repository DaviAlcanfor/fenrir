import { useState } from "react";
import type { Decision, InterruptRequest } from "../lib/api";

export function ApprovalPanel({
  request,
  disabled,
  onResume,
}: {
  request: InterruptRequest;
  disabled?: boolean;
  onResume: (decisions: Decision[]) => void;
}) {
  const actions = request.action_requests ?? [];
  const [reason, setReason] = useState("");

  const decideAll = (make: () => Decision) => onResume(actions.map(make));

  return (
    <div className="approval">
      <strong>approval required</strong>
      {actions.map((a, i) => (
        <div className="action" key={i}>
          <span>
            <b>{a.name}</b> <code>{JSON.stringify(a.args)}</code>
          </span>
        </div>
      ))}
      <div className="action">
        <input
          placeholder="reason (sent if you reject)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </div>
      <div className="action">
        <button disabled={disabled} onClick={() => decideAll(() => ({ type: "approve" }))}>
          approve
        </button>
        <button
          className="ghost"
          disabled={disabled}
          onClick={() => decideAll(() => ({ type: "reject", message: reason || undefined }))}
        >
          reject
        </button>
      </div>
    </div>
  );
}
