import {
  appendLog,
  estimateTokens,
  getRun,
  mapBackendReport,
  patchRun,
  postBackend,
  setAgentStage,
  upsertTool
} from "@/lib/server/research-registry";
import type { AgentNode, ResearchRun, StreamEvent, ToolExecution } from "@/types/research";

export const dynamic = "force-dynamic";

export async function GET(_: Request, { params }: { params: { id: string } }) {
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      const send = (event: StreamEvent) => controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
      const run = getRun(params.id);

      if (!run) {
        send({ type: "error", message: "Research run not found. Start a new workflow from the dashboard." });
        controller.close();
        return;
      }

      if (run.report) {
        send({ type: "complete", run, report: run.report });
        controller.close();
        return;
      }

      try {
        await runBackendPipeline(params.id, send);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown backend error";
        const current = getRun(params.id);
        const failedAgents = current ? setAgentStage(current.agents, activeAgentIndex(current.agents), 100, true) : undefined;
        const log = appendLog(params.id, "system", "error", message);
        const failedRun = patchRun(params.id, {
          status: "failed",
          currentTask: "Backend pipeline failed",
          estimatedCompletion: "Failed",
          agents: failedAgents
        });
        send({ type: "error", run: failedRun, log, message });
      } finally {
        controller.close();
      }
    }
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive"
    }
  });
}

async function runBackendPipeline(id: string, send: (event: StreamEvent) => void) {
  const run = getRun(id);
  if (!run) throw new Error("Research run not found");

  const emitStage = (patch: Partial<ResearchRun>, agent: string, message: string) => {
    const log = appendLog(id, agent, "info", message);
    const nextRun = patchRun(id, patch);
    send({ type: "status", run: nextRun, log });
    return nextRun;
  };

  emitStage(
    {
      status: "running",
      progress: 8,
      currentTask: "Prompt Enhancer Agent is calling the backend",
      estimatedCompletion: "Backend running",
      agents: setAgentStage(run.agents, 0, 45),
      tokenUsage: tokenUsage(run.prompt)
    },
    "prompt",
    "Calling FastAPI /api/enhance-prompt with the submitted prompt."
  );

  const enhancedPrompt = await postBackend<{
    topics: string[];
    research_depth: "quick" | "medium" | "deep";
    required_sections: string[];
    compare_topics: boolean;
    focus_areas: string[];
  }>("/api/enhance-prompt", { prompt: run.prompt });
  enhancedPrompt.research_depth = run.depth;

  let current = patchRun(id, {
    enhancedPrompt,
    progress: 22,
    currentTask: `Enhanced prompt: ${enhancedPrompt.topics.join(" vs ")}`,
    agents: setAgentStage(getRun(id)!.agents, 1, 20),
    tokenUsage: tokenUsage(run.prompt, JSON.stringify(enhancedPrompt))
  });
  send({
    type: "status",
    run: current,
    log: appendLog(id, "prompt", "success", `Backend extracted topics: ${enhancedPrompt.topics.join(", ")}.`)
  });

  emitStage(
    {
      progress: 28,
      currentTask: "Planner Agent is creating backend research tasks",
      agents: setAgentStage(getRun(id)!.agents, 1, 55)
    },
    "planner",
    "Calling FastAPI /api/plan-research with the enhanced prompt."
  );

  const planning = await postBackend<{ tasks: Array<{ task_id: number; topic: string; subtopic: string; search_query: string; description: string }> }>("/api/plan-research", {
    enhanced_prompt: enhancedPrompt
  });

  current = patchRun(id, {
    tasks: planning.tasks,
    progress: 40,
    currentTask: `Planner created ${planning.tasks.length} backend tasks`,
    agents: setAgentStage(getRun(id)!.agents, 2, 18),
    tokenUsage: tokenUsage(run.prompt, JSON.stringify(enhancedPrompt) + JSON.stringify(planning))
  });
  send({
    type: "status",
    run: current,
    log: appendLog(id, "planner", "success", `Backend planner returned ${planning.tasks.length} executable research tasks.`)
  });

  const queuedTools = planning.tasks.slice(0, 6).map((task) => {
    const tool: ToolExecution = {
      id: `task-${task.task_id}`,
      name: "Web Search Tool",
      query: task.search_query,
      status: "queued",
      durationMs: 0,
      sources: 0
    };
    upsertTool(id, tool);
    return tool;
  });

  emitStage(
    {
      progress: 48,
      currentTask: "Worker Agent is executing backend web research",
      tools: queuedTools,
      agents: setAgentStage(getRun(id)!.agents, 2, 60)
    },
    "worker",
    "Calling FastAPI /api/execute-research. This is the real web-search and summarization step."
  );

  const execution = await postBackend<{ results: Array<{ task_id: number; topic: string; subtopic: string; status: string; findings: string; sources: Array<{ title: string; url: string; snippet: string }>; execution_time_seconds: number; error_message?: string | null }> }>("/api/execute-research", {
    tasks: planning.tasks
  });

  const completedTools = execution.results.slice(0, 8).map((result) => {
    const task = planning.tasks.find((item) => item.task_id === result.task_id);
    const tool: ToolExecution = {
      id: `task-${result.task_id}`,
      name: "Web Search Tool",
      query: task?.search_query || `${result.topic} ${result.subtopic}`,
      status: result.status === "completed" || result.sources.length > 0 ? "completed" : "failed",
      durationMs: Math.round(result.execution_time_seconds * 1000),
      sources: result.sources.length
    };
    upsertTool(id, tool);
    return tool;
  });

  current = patchRun(id, {
    results: execution.results,
    progress: 72,
    currentTask: `Worker completed ${execution.results.filter((result) => result.status === "completed").length}/${execution.results.length} backend tasks`,
    tools: completedTools,
    agents: setAgentStage(getRun(id)!.agents, 4, 30),
    tokenUsage: tokenUsage(run.prompt, JSON.stringify(enhancedPrompt) + JSON.stringify(planning) + JSON.stringify(execution))
  });
  send({
    type: "tool",
    run: current,
    tool: completedTools.at(-1),
    log: appendLog(id, "web", "success", `Backend returned ${execution.results.reduce((sum, result) => sum + result.sources.length, 0)} cited sources across executed tasks.`)
  });

  emitStage(
    {
      progress: 84,
      currentTask: "Formatter Agent is composing the backend report",
      agents: setAgentStage(getRun(id)!.agents, 4, 70)
    },
    "formatter",
    "Calling FastAPI /api/format-report with real task results."
  );

  const backendReport = await postBackend<{
    title: string;
    topics: string[];
    introduction: string;
    sections: Record<string, string>;
    comparative_analysis?: string | null;
    conclusion: string;
    citations: Array<{ title: string; url: string; snippet: string }>;
    generated_at: string;
    total_words: number;
  }>("/api/format-report", {
    task_results: execution.results,
    enhanced_prompt: enhancedPrompt
  });
  const report = mapBackendReport(id, backendReport);

  current = patchRun(id, {
    report,
    status: "completed",
    progress: 100,
    currentTask: "Report ready",
    estimatedCompletion: "Complete",
    agents: getRun(id)!.agents.map((agent) => ({ ...agent, status: "completed", progress: 100 })),
    tokenUsage: tokenUsage(run.prompt, JSON.stringify(backendReport))
  });

  send({
    type: "complete",
    run: current,
    report,
    log: appendLog(id, "formatter", "success", `Backend generated report for: ${report.topics.join(", ")}.`)
  });
}

function tokenUsage(prompt: string, generated = "") {
  const promptTokens = estimateTokens(prompt);
  const completionTokens = estimateTokens(generated);
  return {
    prompt: promptTokens,
    completion: completionTokens,
    total: promptTokens + completionTokens
  };
}

function activeAgentIndex(agents: AgentNode[]) {
  const index = agents.findIndex((agent) => agent.status === "running");
  return index === -1 ? 0 : index;
}
