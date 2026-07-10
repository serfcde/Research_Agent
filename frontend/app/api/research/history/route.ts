import { NextResponse } from "next/server";
import { agentTemplate } from "@/lib/mock-data";
import { getBackend, listRuns } from "@/lib/server/research-registry";
import type { ResearchRun } from "@/types/research";

export async function GET() {
  const local = listRuns();
  const seen = new Set(local.map((run) => run.id));
  const merged: ResearchRun[] = [...local];

  // Merge in runs the backend persisted before/beyond this frontend process.
  try {
    const backend = await getBackend<{ runs: Array<{ id: string; prompt: string; status: string; created_at: string; finished_at?: string | null }> }>(
      "/api/runs"
    );
    for (const run of backend?.runs ?? []) {
      if (seen.has(run.id)) continue;
      const status = run.status === "completed" ? "completed" : run.status === "failed" ? "failed" : "running";
      merged.push({
        id: run.id,
        prompt: run.prompt,
        depth: "medium",
        status,
        progress: status === "completed" ? 100 : 0,
        currentTask: status === "completed" ? "Report ready" : `Backend status: ${run.status}`,
        createdAt: run.created_at,
        estimatedCompletion: status === "completed" ? "Complete" : "Unknown",
        tokenUsage: { prompt: 0, completion: 0, total: 0 },
        agents: agentTemplate.map((agent) => ({ ...agent, status: status === "completed" ? "completed" as const : "queued" as const, progress: status === "completed" ? 100 : 0 })),
        logs: [],
        tools: [],
      });
    }
  } catch (error) {
    console.error("Backend history lookup failed:", error);
  }

  merged.sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
  return NextResponse.json(merged);
}
