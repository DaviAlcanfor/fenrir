"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { useRef, useState } from "react";
import type { Decision, InterruptRequest } from "@/lib/api";

export function ApprovalPanel({
  request,
  disabled,
  onResume,
}: {
  request: InterruptRequest;
  disabled?: boolean;
  onResume: (decisions: Decision[]) => void;
}) {
  const root = useRef<HTMLDivElement>(null);
  const actions = request.action_requests ?? [];
  const [reason, setReason] = useState("");

  useGSAP(
    () => {
      gsap.from(root.current, { autoAlpha: 0, y: 10, scale: 0.98, duration: 0.35, ease: "power2.out" });
    },
    { scope: root },
  );

  const decideAll = (make: () => Decision) => onResume(actions.map(make));

  return (
    <div className="approval" ref={root}>
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
