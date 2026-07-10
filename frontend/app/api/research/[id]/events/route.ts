// app/api/research/[id]/events/route.ts
//
// Thin SSE proxy: the FastAPI backend owns orchestration and streams
// tracker events (run_start / node_start / node_end / run_end); this
// route consumes that stream, rebuilds the span tree + UI run state
// from the events, and re-emits StreamEvents for the browser.
// The run id doubles as backend run_id and trace id.

import {
  appendLog, estimateTokens, getBackend, getBackendUrl, backendHeaders, getRun, mapBackendReport,
  patchRun, setAgentStage, upsertTool,
} from "@/lib/server/research-registry";
import {
  createTrace, endSpan, spansToGraph, startSpan, type Span, type TraceContext,
} from "@/lib/server/trace";
import type { AgentStep, LogLevel, StreamEvent, ToolExecution } from "@/types/research";

export const dynamic = "force-dynamic";

interface TrackerEvent {
  run_id: string;
  event_type: "run_start" | "node_start" | "node_end" | "run_end" | string;
  node: string;
  ts: number | null;
  data: Record<string, any>;
}

const NODE_META: Record<string, { index: number; label: string; startProgress: number; endProgress: number }> = {
  prompt_enhancer: { index: 0, label: "Prompt Enhancer", startProgress: 8, endProgress: 20 },
  planner: { index: 1, label: "Planner Agent", startProgress: 26, endProgress: 40 },
  worker: { index: 2, label: "Worker Agent", startProgress: 46, endProgress: 68 },
  critic: { index: 3, label: "Critic Agent", startProgress: 72, endProgress: 80 },
  formatter: { index: 4, label: "Formatter Agent", startProgress: 84, endProgress: 97 },
};

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
        await proxyBackendEvents(params.id, send);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        const log = appendLog(params.id, "system", "error", message);
        const failedRun = patchRun(params.id, { status: "failed", currentTask: "Pipeline failed" });
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

async function proxyBackendEvents(id: string, send: (event: StreamEvent) => void) {
  const response = await fetch(`${getBackendUrl()}/api/research/${id}/events`, {
    headers: backendHeaders({ Accept: "text/event-stream" }),
    cache: "no-store",
  });
  if (!response.ok || !response.body) {
    throw new Error(`Backend event stream failed with ${response.status}`);
  }

  const trace: TraceContext = createTrace();
  trace.trace_id = id;
  const steps: AgentStep[] = [];
  const rootSpan = startSpan(trace, "research_run", null, { run_id: id });
  const openSpans: Record<string, Span> = {};
  let lastSpanId = rootSpan.span_id;
  let totalTokens = 0;

  const log = (agent: string, level: LogLevel, message: string) => appendLog(id, agent, level, message);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const chunk = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const dataLine = chunk.split("\n").find((line) => line.startsWith("data: "));
      if (!dataLine) continue; // heartbeat / comment

      const event = JSON.parse(dataLine.slice(6)) as TrackerEvent;
      const finished = await handleEvent(event);
      if (finished) return;
    }
  }

  // Stream ended without run_end — resolve final state from the run record.
  await finalize();

  async function handleEvent(event: TrackerEvent): Promise<boolean> {
    const meta = NODE_META[event.node];

    if (event.event_type === "node_start" && meta) {
      const input = event.data?.input ?? {};
      const iteration = input.iteration ?? 0;
      const replanning = event.node === "planner" && iteration > 0;
      const span = startSpan(trace, event.node, lastSpanId, {
        transition_label: replanning ? `replan (iteration ${iteration + 1})` : meta.label.toLowerCase(),
      });
      openSpans[event.node] = span;

      const current = getRun(id)!;
      const next = patchRun(id, {
        status: "running",
        progress: Math.max(current.progress, meta.startProgress),
        currentTask: replanning ? "Planner filling coverage gaps" : `${meta.label} running`,
        agents: setAgentStage(current.agents, meta.index, 50),
      });
      send({ type: "status", run: next, log: log(event.node, "info", `[trace:${id}][span:${span.span_id}] ${meta.label} started${replanning ? " (replanning)" : ""}`) });
      return false;
    }

    if (event.event_type === "node_end" && meta) {
      const output = event.data?.output ?? {};
      const error = event.data?.error;
      const span = openSpans[event.node];
      if (span) {
        endSpan(span, { duration_ms: event.data?.duration_ms ?? 0, ...scalarAttributes(output), ...(error ? { error } : {}) });
        lastSpanId = span.span_id;
        const tokens = estimateTokens(JSON.stringify(output));
        totalTokens += tokens;
        steps.push({
          agentId: span.span_id, agentName: meta.label,
          prompt: JSON.stringify(event.data?.input ?? {}, null, 2),
          output: JSON.stringify(output, null, 2),
          durationMs: event.data?.duration_ms ?? 0, tokens,
          traceId: span.trace_id, spanId: span.span_id, parentSpanId: span.parent_span_id,
          pipelockRequestIds: span.pipelock_request_ids,
        });
      }

      if (error) {
        const current = getRun(id)!;
        const failed = patchRun(id, {
          status: "failed", currentTask: `${meta.label} failed`,
          agents: setAgentStage(current.agents, meta.index, 100, true),
        });
        send({ type: "error", run: failed, log: log(event.node, "error", `${meta.label} failed: ${error}`), message: error });
        return false; // wait for run_end for terminal bookkeeping
      }

      applyNodeOutput(event.node, output);

      const current = getRun(id)!;
      const next = patchRun(id, {
        progress: Math.max(current.progress, meta.endProgress),
        steps: [...steps],
        agents: setAgentStage(current.agents, Math.min(meta.index + 1, 4), meta.index === 4 ? 100 : 10),
        tokenUsage: { prompt: estimateTokens(current.prompt), completion: totalTokens, total: estimateTokens(current.prompt) + totalTokens },
      });
      send({ type: "status", run: next, log: log(event.node, "success", nodeSummaryMessage(event.node, output)) });
      return false;
    }

    if (event.event_type === "run_end") {
      await finalize(event.data?.status);
      return true;
    }

    return false;
  }

  function applyNodeOutput(node: string, output: Record<string, any>) {
    if (node === "prompt_enhancer" && output.topics) {
      patchRun(id, { currentTask: `Topics: ${(output.topics as string[]).join(" vs ")}` });
    }
    if (node === "planner" && Array.isArray(output.tasks)) {
      for (const task of output.tasks) {
        const tool: ToolExecution = {
          id: `task-${task.task_id}`, name: "Web Search Tool",
          query: task.search_query, status: "queued", durationMs: 0, sources: 0,
        };
        upsertTool(id, tool);
        send({ type: "tool", tool });
      }
    }
    if (node === "worker" && Array.isArray(output.results)) {
      for (const result of output.results) {
        const tool: ToolExecution = {
          id: `task-${result.task_id}`, name: "Web Search Tool",
          query: result.search_query || result.subtopic,
          status: result.status === "failed" ? "failed" : "completed",
          durationMs: Math.round((result.seconds ?? 0) * 1000), sources: result.sources ?? 0,
        };
        upsertTool(id, tool);
        send({ type: "tool", tool });
      }
    }
    if (node === "critic") {
      const verdict = output.verdict === "needs_more" ? "requested another research pass" : "approved coverage";
      patchRun(id, { currentTask: `Critic ${verdict} (coverage ${(Number(output.coverage_score ?? 0) * 100).toFixed(0)}%)` });
    }
  }

  async function finalize(status?: string) {
    endSpan(rootSpan, { status: status ?? "completed" });
    const { nodes, edges } = spansToGraph(trace.spans);

    const backendRun = await getBackend<{
      status: string; error?: string | null;
      report?: { report: any; file_path?: string } | null;
    }>(`/api/research/${id}`);

    if (backendRun?.status === "completed" && backendRun.report?.report) {
      const report = mapBackendReport(id, backendRun.report.report);
      report.filePath = backendRun.report.file_path;
      const current = getRun(id)!;
      const next = patchRun(id, {
        report, steps: [...steps], traceId: id, traceSpans: trace.spans,
        traceGraph: { nodes, edges },
        status: "completed", progress: 100, currentTask: "Report ready", estimatedCompletion: "Complete",
        agents: current.agents.map((a) => ({ ...a, status: "completed" as const, progress: 100 })),
      });
      send({ type: "complete", run: next, report, log: log("formatter", "success", `[trace:${id}] Complete — ${trace.spans.length} spans`) });
      return;
    }

    const message = backendRun?.error || "Research run failed";
    const next = patchRun(id, {
      status: "failed", currentTask: "Pipeline failed", traceSpans: trace.spans, traceGraph: { nodes, edges },
    });
    send({ type: "error", run: next, log: log("system", "error", message), message });
  }
}

function scalarAttributes(output: Record<string, any>): Record<string, string | number> {
  const attrs: Record<string, string | number> = {};
  for (const [key, value] of Object.entries(output)) {
    if (typeof value === "string" || typeof value === "number") attrs[key] = value;
    if (Array.isArray(value) && value.every((v) => typeof v === "string")) attrs[key] = value.join(", ");
  }
  return attrs;
}

function nodeSummaryMessage(node: string, output: Record<string, any>): string {
  switch (node) {
    case "prompt_enhancer":
      return `Topics: ${(output.topics ?? []).join(", ")} (depth: ${output.research_depth ?? "medium"})`;
    case "planner":
      return `${output.task_count ?? 0} research tasks planned${(output.iteration ?? 0) > 0 ? ` (gap-filling pass ${output.iteration})` : ""}`;
    case "worker":
      return `${output.completed ?? 0}/${output.total ?? 0} tasks completed`;
    case "critic":
      return `Verdict: ${output.verdict ?? "sufficient"} — coverage ${(Number(output.coverage_score ?? 0) * 100).toFixed(0)}%${(output.gaps ?? []).length ? `, gaps: ${(output.gaps as string[]).join("; ")}` : ""}`;
    case "formatter":
      return `Report ready — ${output.total_words ?? 0} words, ${output.citations ?? 0} citations`;
    default:
      return `${node} finished`;
  }
}
