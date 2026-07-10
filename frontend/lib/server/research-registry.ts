import "server-only";

import { agentTemplate } from "@/lib/mock-data";
import type { ActivityLog, AgentNode, AgentStatus, LogLevel, ResearchDepth, ResearchReport, ResearchRun, ToolExecution } from "@/types/research";

interface BackendSource {
  title: string;
  url: string;
  snippet: string;
}

interface BackendEnhancedPrompt {
  topics: string[];
  research_depth: ResearchDepth;
  required_sections: string[];
  compare_topics: boolean;
  focus_areas: string[];
}

interface BackendTask {
  task_id: number;
  topic: string;
  subtopic: string;
  search_query: string;
  description: string;
}

interface BackendTaskResult {
  task_id: number;
  topic: string;
  subtopic: string;
  status: string;
  findings: string;
  sources: BackendSource[];
  execution_time_seconds: number;
  error_message?: string | null;
}

interface BackendReport {
  title: string;
  topics: string[];
  introduction: string;
  sections: Record<string, string>;
  comparative_analysis?: string | null;
  conclusion: string;
  citations: BackendSource[];
  generated_at: string;
  total_words: number;
}

interface StoredRun extends ResearchRun {
  enhancedPrompt?: BackendEnhancedPrompt;
  tasks?: BackendTask[];
  results?: BackendTaskResult[];
}

const registry = globalThis as typeof globalThis & {
  __agenticResearchRuns?: Map<string, StoredRun>;
};

export const runs = registry.__agenticResearchRuns ?? new Map<string, StoredRun>();
registry.__agenticResearchRuns = runs;

export function createRun(prompt: string, depth: ResearchDepth): ResearchRun {
  const id = `ars-${Date.now()}`;
  const run: ResearchRun = {
    id,
    prompt,
    depth,
    status: "queued",
    progress: 0,
    currentTask: "Queued for backend orchestration",
    createdAt: new Date().toISOString(),
    estimatedCompletion: "Starting",
    tokenUsage: { prompt: 0, completion: 0, total: 0 },
    agents: agentTemplate.map((agent) => ({ ...agent, status: "queued", progress: 0 })),
    logs: [createLog("system", "info", "Research workflow created from dashboard input.")],
    tools: []
  };
  runs.set(id, run);
  return run;
}

export function getRun(id: string) {
  return runs.get(id);
}

export function listRuns() {
  return Array.from(runs.values()).sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
}

export function patchRun(id: string, patch: Partial<StoredRun>) {
  const current = runs.get(id);
  if (!current) return undefined;
  const next = { ...current, ...patch };
  runs.set(id, next);
  return next;
}

export function appendLog(id: string, agent: string, level: LogLevel, message: string) {
  const current = runs.get(id);
  if (!current) return undefined;
  const log = createLog(agent, level, message);
  patchRun(id, { logs: [...current.logs, log] });
  return log;
}

export function upsertTool(id: string, tool: ToolExecution) {
  const current = runs.get(id);
  if (!current) return undefined;
  const tools = [...current.tools.filter((item) => item.id !== tool.id), tool];
  patchRun(id, { tools });
  return tool;
}

export function setAgentStage(agents: AgentNode[], activeIndex: number, activeProgress: number, failed = false) {
  return agents.map((agent, index) => {
    const status: AgentStatus = failed && index === activeIndex ? "failed" : index < activeIndex ? "completed" : index === activeIndex ? "running" : "queued";
    return {
      ...agent,
      status,
      progress: index < activeIndex ? 100 : index === activeIndex ? activeProgress : 0
    };
  });
}

export function getBackendUrl() {
  return process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_BACKEND_API_URL || "http://127.0.0.1:8000";
}

export function backendHeaders(extra: Record<string, string> = {}) {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...extra };
  // Server-side only: never exposed to the browser.
  if (process.env.BACKEND_API_KEY) headers["X-API-Key"] = process.env.BACKEND_API_KEY;
  return headers;
}

export async function postBackend<T>(path: string, body: unknown, extraHeaders: Record<string, string> = {}): Promise<T> {
  const response = await fetch(`${getBackendUrl()}${path}`, {
    method: "POST",
    headers: backendHeaders(extraHeaders),
    body: JSON.stringify(body),
    cache: "no-store"
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${path} failed with ${response.status}: ${text}`);
  }
  return response.json() as Promise<T>;
}

export async function getBackend<T>(path: string): Promise<T | undefined> {
  const response = await fetch(`${getBackendUrl()}${path}`, {
    headers: backendHeaders(),
    cache: "no-store"
  });
  if (response.status === 404) return undefined;
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${path} failed with ${response.status}: ${text}`);
  }
  return response.json() as Promise<T>;
}

export function mapBackendReport(id: string, report: BackendReport): ResearchReport {
  const sectionText = Object.values(report.sections).join(" ");
  const insights = extractInsights(`${sectionText} ${report.comparative_analysis || ""} ${report.conclusion}`);
  return {
    id,
    title: report.title,
    topics: report.topics,
    introduction: report.introduction,
    sections: report.sections,
    comparativeAnalysis: report.comparative_analysis || "No comparative analysis was generated for this research request.",
    keyInsights: insights,
    conclusion: report.conclusion,
    citations: report.citations || [],
    generatedAt: report.generated_at,
    totalWords: report.total_words
  };
}

export function reportToText(report: ResearchReport) {
  return [
    report.title,
    "",
    report.introduction,
    "",
    ...Object.entries(report.sections).flatMap(([title, content]) => [`## ${title}`, content, ""]),
    "## Comparative Analysis",
    report.comparativeAnalysis,
    "",
    "## Key Insights",
    ...report.keyInsights.map((insight) => `- ${insight}`),
    "",
    "## Conclusion",
    report.conclusion,
    "",
    "## Citations",
    ...report.citations.map((source) => `- ${source.title}: ${source.url}`)
  ].join("\n");
}

export function estimateTokens(text: string) {
  return Math.max(0, Math.round(text.length / 4));
}

function createLog(agent: string, level: LogLevel, message: string): ActivityLog {
  return {
    id: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
    level,
    agent,
    message
  };
}

function extractInsights(text: string) {
  const sentences = text
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter((sentence) => sentence.length > 80);

  return sentences.slice(0, 4).length
    ? sentences.slice(0, 4)
    : [
        "The generated report did not include enough long-form findings to derive separate key insights.",
        "Review the topic sections and conclusion for the most important takeaways."
      ];
}
