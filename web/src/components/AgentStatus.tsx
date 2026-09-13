export type AgentState = "thinking" | "responded" | "terminated";
export type AgentInfo = { status: AgentState; action?: string };
