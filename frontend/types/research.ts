export type ResearchDepth = "quick" | "medium" | "deep";
export type AgentStatus = "idle" | "queued" | "running" | "completed" | "failed";
export type LogLevel = "info" | "success" | "warning" | "error" | "tool";

export interface AgentNode {
  id: string;
  name: string;
  role: string;
  status: AgentStatus;
  progress: number;
  latencyMs?: number;
  tokens?: number;
}

export interface ActivityLog {
  id: string;
  timestamp: string;
  level: LogLevel;
  agent: string;
  message: string;
}

export interface ToolExecution {
  id: string;
  name: string;
  query: string;
  status: AgentStatus;
  durationMs: number;
  sources: number;
}

export interface ResearchReport {
  id: string;
  title: string;
  topics: string[];
  introduction: string;
  sections: Record<string, string>;
  comparativeAnalysis: string;
  keyInsights: string[];
  conclusion: string;
  citations: Array<{ title: string; url: string; snippet: string }>;
  generatedAt: string;
  totalWords: number;
  filePath?: string;
}

export interface ResearchRun {
  id: string;
  prompt: string;
  depth: ResearchDepth;
  status: AgentStatus;
  progress: number;
  currentTask: string;
  createdAt: string;
  estimatedCompletion: string;
  tokenUsage: {
    prompt: number;
    completion: number;
    total: number;
  };
  agents: AgentNode[];
  logs: ActivityLog[];
  tools: ToolExecution[];
  report?: ResearchReport;
}

export interface StartResearchPayload {
  prompt: string;
  depth: ResearchDepth;
}

export interface SettingsState {
  apiBaseUrl: string;
  backendApiUrl: string;
  notifications: boolean;
  autoDownload: boolean;
  profileName: string;
  profileEmail: string;
}

export interface StreamEvent {
  type: "status" | "log" | "tool" | "report" | "complete" | "error";
  run?: Partial<ResearchRun>;
  log?: ActivityLog;
  tool?: ToolExecution;
  report?: ResearchReport;
  message?: string;
}
