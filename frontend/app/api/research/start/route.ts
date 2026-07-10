import { NextResponse } from "next/server";
import { createRun, patchRun, postBackend } from "@/lib/server/research-registry";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    if (!body?.prompt || typeof body.prompt !== "string") {
      return NextResponse.json({ error: "prompt is required" }, { status: 400 });
    }

    // Registry run holds UI state; the backend owns orchestration.
    const run = createRun(body.prompt, body.depth ?? "medium");

    // The run id doubles as the backend run_id AND the trace id
    // (sent as X-Trace-Id), so frontend spans, backend tracker events
    // and Pipelock request ids all correlate on one identifier.
    await postBackend<{ run_id: string; status: string }>(
      "/api/research",
      { prompt: body.prompt },
      { "X-Trace-Id": run.id }
    );

    patchRun(run.id, { status: "running", currentTask: "Backend pipeline started", traceId: run.id });
    return NextResponse.json({ id: run.id, status: "running" });
  } catch (error) {
    console.error("Start research error:", error);
    return NextResponse.json({ error: "Failed to start research" }, { status: 500 });
  }
}
