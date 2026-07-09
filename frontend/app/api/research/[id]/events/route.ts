// app/api/research/[id]/events/route.ts
// Full tracing — trace_id, span_id, parent_span_id at every step
// Pipelock request_ids attached to each span

import {
  appendLog, estimateTokens, getRun, mapBackendReport,
  patchRun, setAgentStage, upsertTool,
} from "@/lib/server/research-registry";
import {
  attachPipelockRequestId, createTrace, endSpan,
  spansToGraph, startSpan, type Span, type TraceContext,
} from "@/lib/server/trace";
import type { AgentNode, AgentStep, ResearchRun, StreamEvent, ToolExecution } from "@/types/research";

export const dynamic = "force-dynamic";

// Wraps fetch to extract Pipelock's request_id from response headers
async function postBackendTraced<T>(path: string, body: unknown, span: Span): Promise<T> {
  const backendUrl = process.env.BACKEND_API_URL || "http://127.0.0.1:8000";
  const response = await fetch(`${backendUrl}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Trace-Id": span.trace_id,
      "X-Span-Id": span.span_id,
    },
    body: JSON.stringify(body),
    cache: "no-store",
  });

  // Pipelock injects X-Pipelock-Request-Id on proxied responses
  const pipelockReqId = response.headers.get("x-pipelock-request-id") || response.headers.get("X-Pipelock-Request-Id");
  if (pipelockReqId) attachPipelockRequestId(span, pipelockReqId);

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${path} failed ${response.status}: ${text}`);
  }
  return response.json() as Promise<T>;
}

export async function GET(_: Request, { params }: { params: { id: string } }) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const send = (event: StreamEvent) =>
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
      const run = getRun(params.id);

      if (!run) {
        send({ type: "error", message: "Research run not found. Start a new workflow from the dashboard." });
        controller.close(); return;
      }
      if (run.report) {
        send({ type: "complete", run, report: run.report });
        controller.close(); return;
      }

      try {
        await runBackendPipeline(params.id, send);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        const current = getRun(params.id);
        const failedAgents = current ? setAgentStage(current.agents, activeAgentIndex(current.agents), 100, true) : undefined;
        const log = appendLog(params.id, "system", "error", message);
        const failedRun = patchRun(params.id, { status: "failed", currentTask: "Pipeline failed", agents: failedAgents });
        send({ type: "error", run: failedRun, log, message });
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache, no-transform", Connection: "keep-alive" },
  });
}

async function runBackendPipeline(id: string, send: (event: StreamEvent) => void) {
  const run = getRun(id);
  if (!run) throw new Error("Research run not found");

  const trace: TraceContext = createTrace();
  const steps: AgentStep[] = [];

  const emit = (patch: Partial<ResearchRun>, agent: string, message: string) => {
    const log = appendLog(id, agent, "info", message);
    const next = patchRun(id, patch);
    send({ type: "status", run: next, log });
    return next;
  };

  // Root span
  const rootSpan = startSpan(trace, "research_run", null, { prompt: run.prompt });

  // ── Prompt Enhancer ──────────────────────────────────────────────────────
  const promptSpan = startSpan(trace, "prompt_enhancer", rootSpan.span_id, { transition_label: "raw prompt" });
  emit({ status: "running", progress: 8, currentTask: "Prompt Enhancer running", agents: setAgentStage(run.agents, 0, 45), tokenUsage: tokenUsage(run.prompt) },
    "prompt", `[trace:${trace.trace_id}][span:${promptSpan.span_id}] /api/enhance-prompt`);

  const enhancedPrompt = await postBackendTraced<{
    topics: string[]; research_depth: "quick"|"medium"|"deep"; required_sections: string[]; compare_topics: boolean; focus_areas: string[];
  }>("/api/enhance-prompt", { prompt: run.prompt }, promptSpan);
  enhancedPrompt.research_depth = run.depth;
  endSpan(promptSpan, { topics: enhancedPrompt.topics.join(", ") });
  steps.push(toStep(promptSpan, "Prompt Enhancer", run.prompt,
    JSON.stringify({ topics: enhancedPrompt.topics, depth: enhancedPrompt.research_depth }, null, 2),
    estimateTokens(run.prompt + JSON.stringify(enhancedPrompt))));

  let current = patchRun(id, { enhancedPrompt, steps, traceId: trace.trace_id, progress: 22,
    currentTask: `Topics: ${enhancedPrompt.topics.join(" vs ")}`, agents: setAgentStage(getRun(id)!.agents, 1, 20),
    tokenUsage: tokenUsage(run.prompt, JSON.stringify(enhancedPrompt)) });
  send({ type: "status", run: current, log: appendLog(id, "prompt", "success", `[span:${promptSpan.span_id}] Topics: ${enhancedPrompt.topics.join(", ")}`) });

  // ── Planner ──────────────────────────────────────────────────────────────
  const plannerSpan = startSpan(trace, "planner_agent", promptSpan.span_id, { transition_label: "enhanced prompt" });
  emit({ progress: 28, currentTask: "Planner creating tasks", agents: setAgentStage(getRun(id)!.agents, 1, 55) },
    "planner", `[trace:${trace.trace_id}][span:${plannerSpan.span_id}][parent:${plannerSpan.parent_span_id}] /api/plan-research`);

  const planning = await postBackendTraced<{
    tasks: Array<{ task_id: number; topic: string; subtopic: string; search_query: string; description: string }>;
  }>("/api/plan-research", { enhanced_prompt: enhancedPrompt }, plannerSpan);
  endSpan(plannerSpan, { task_count: planning.tasks.length });
  steps.push(toStep(plannerSpan, "Planner Agent",
    `Create research plan for: ${enhancedPrompt.topics.join(", ")}`,
    planning.tasks.map((t, i) => `${i + 1}. ${t.description}\n   Query: "${t.search_query}"`).join("\n"),
    estimateTokens(JSON.stringify(planning))));

  current = patchRun(id, { tasks: planning.tasks, steps, progress: 40, currentTask: `${planning.tasks.length} tasks created`,
    agents: setAgentStage(getRun(id)!.agents, 2, 18), tokenUsage: tokenUsage(run.prompt, JSON.stringify(enhancedPrompt) + JSON.stringify(planning)) });
  send({ type: "status", run: current, log: appendLog(id, "planner", "success", `[span:${plannerSpan.span_id}] ${planning.tasks.length} tasks`) });

  // ── Worker ───────────────────────────────────────────────────────────────
  const workerSpan = startSpan(trace, "worker_agent", plannerSpan.span_id, { transition_label: `${planning.tasks.length} tasks` });
  const queuedTools = planning.tasks.slice(0, 6).map((task) => {
    const tool: ToolExecution = { id: `task-${task.task_id}`, name: "Web Search Tool", query: task.search_query, status: "queued", durationMs: 0, sources: 0 };
    upsertTool(id, tool); return tool;
  });
  emit({ progress: 48, currentTask: "Worker executing searches", tools: queuedTools, agents: setAgentStage(getRun(id)!.agents, 2, 60) },
    "worker", `[trace:${trace.trace_id}][span:${workerSpan.span_id}][parent:${workerSpan.parent_span_id}] /api/execute-research`);

  const execution = await postBackendTraced<{
    results: Array<{ task_id: number; topic: string; subtopic: string; status: string; findings: string; sources: Array<{ title: string; url: string; snippet: string }>; execution_time_seconds: number }>;
  }>("/api/execute-research", { tasks: planning.tasks }, workerSpan);
  endSpan(workerSpan, { completed: execution.results.filter(r => r.status === "completed").length });
  steps.push(toStep(workerSpan, "Worker Agent",
    planning.tasks.map(t => `• ${t.search_query}`).join("\n"),
    execution.results.map(r => `[${r.topic}] ${r.subtopic}: ${r.findings.slice(0, 120)}...\n  Sources: ${r.sources.length}`).join("\n\n"),
    estimateTokens(JSON.stringify(execution))));

  // Tool child spans
  const completedTools = execution.results.slice(0, 8).map((result, i) => {
    const task = planning.tasks.find(t => t.task_id === result.task_id);
    const toolSpan = startSpan(trace, `web_search_${i + 1}`, workerSpan.span_id,
      { transition_label: "search", query: task?.search_query || result.subtopic, domain: "api.tavily.com" });
    endSpan(toolSpan, { sources: result.sources.length, duration_s: result.execution_time_seconds });
    steps.push(toStep(toolSpan, `Web Search: ${result.subtopic}`,
      task?.search_query || result.subtopic,
      result.findings.slice(0, 400) + (result.findings.length > 400 ? "..." : ""),
      estimateTokens(result.findings)));
    const tool: ToolExecution = {
      id: `task-${result.task_id}`, name: "Web Search Tool",
      query: task?.search_query || result.subtopic,
      status: result.status === "completed" || result.sources.length > 0 ? "completed" : "failed",
      durationMs: Math.round(result.execution_time_seconds * 1000), sources: result.sources.length,
    };
    upsertTool(id, tool); return tool;
  });

  current = patchRun(id, { results: execution.results, steps, progress: 72,
    currentTask: `${execution.results.filter(r => r.status === "completed").length}/${execution.results.length} tasks done`,
    tools: completedTools, agents: setAgentStage(getRun(id)!.agents, 4, 30),
    tokenUsage: tokenUsage(run.prompt, JSON.stringify(enhancedPrompt) + JSON.stringify(planning) + JSON.stringify(execution)) });
  send({ type: "tool", run: current, tool: completedTools.at(-1),
    log: appendLog(id, "web", "success", `[span:${workerSpan.span_id}] ${execution.results.reduce((s, r) => s + r.sources.length, 0)} sources`) });

  // ── Formatter ────────────────────────────────────────────────────────────
  const formatterSpan = startSpan(trace, "formatter_agent", workerSpan.span_id, { transition_label: "findings" });
  emit({ progress: 84, currentTask: "Formatter composing report", agents: setAgentStage(getRun(id)!.agents, 4, 70) },
    "formatter", `[trace:${trace.trace_id}][span:${formatterSpan.span_id}][parent:${formatterSpan.parent_span_id}] /api/format-report`);

  const backendReport = await postBackendTraced<{
    title: string; topics: string[]; introduction: string; sections: Record<string, string>;
    comparative_analysis?: string | null; conclusion: string;
    citations: Array<{ title: string; url: string; snippet: string }>;
    generated_at: string; total_words: number;
  }>("/api/format-report", { task_results: execution.results, enhanced_prompt: enhancedPrompt }, formatterSpan);

  const report = mapBackendReport(id, backendReport);
  endSpan(formatterSpan, { words: backendReport.total_words, citations: backendReport.citations.length });
  steps.push(toStep(formatterSpan, "Formatter Agent",
    `Format findings for: ${enhancedPrompt.topics.join(", ")}`,
    `Title: ${backendReport.title}\nSections: ${Object.keys(backendReport.sections).join(", ")}\nWords: ${backendReport.total_words}\nCitations: ${backendReport.citations.length}`,
    estimateTokens(JSON.stringify(backendReport))));

  endSpan(rootSpan, { status: "completed" });
  const { nodes: traceNodes, edges: traceEdges } = spansToGraph(trace.spans);

  current = patchRun(id, {
    report, steps, traceId: trace.trace_id, traceSpans: trace.spans,
    traceGraph: { nodes: traceNodes, edges: traceEdges },
    status: "completed", progress: 100, currentTask: "Report ready", estimatedCompletion: "Complete",
    agents: getRun(id)!.agents.map(a => ({ ...a, status: "completed", progress: 100 })),
    tokenUsage: tokenUsage(run.prompt, JSON.stringify(backendReport)),
  });

  send({ type: "complete", run: current, report,
    log: appendLog(id, "formatter", "success", `[trace:${trace.trace_id}] Complete — ${trace.spans.length} spans`) });
}

function toStep(span: Span, name: string, prompt: string, output: string, tokens?: number): AgentStep {
  return { agentId: span.span_id, agentName: name, prompt, output, durationMs: span.duration_ms || 0, tokens,
    traceId: span.trace_id, spanId: span.span_id, parentSpanId: span.parent_span_id,
    pipelockRequestIds: span.pipelock_request_ids };
}

function tokenUsage(prompt: string, generated = "") {
  const p = estimateTokens(prompt), c = estimateTokens(generated);
  return { prompt: p, completion: c, total: p + c };
}

function activeAgentIndex(agents: AgentNode[]) {
  const i = agents.findIndex(a => a.status === "running");
  return i === -1 ? 0 : i;
}