const COLOR: Record<string, string> = {
  recon: "#4fc3f7",
  web: "#ba68c8",
  exploit: "#ff8a65",
  triage: "#81c784",
  orchestrator: "#90a4ae",
  model: "#90a4ae", // deepagents' root node name
};

export const colorFor = (node?: string | null): string => (node && COLOR[node]) || "#3a4149";
