import { NextResponse } from "next/server";
import { getBackend, getRun } from "@/lib/server/research-registry";

export async function GET(_: Request, { params }: { params: { id: string } }) {
  const run = getRun(params.id);
  if (run) return NextResponse.json(run);

  // Registry is in-memory; after a frontend restart fall back to the
  // backend's durable run store.
  try {
    const backendRun = await getBackend<{ id: string; prompt: string; status: string; created_at: string }>(
      `/api/research/${params.id}`
    );
    if (backendRun) {
      return NextResponse.json({
        id: backendRun.id,
        prompt: backendRun.prompt,
        status: backendRun.status === "running" ? "running" : backendRun.status,
        progress: backendRun.status === "completed" ? 100 : 0,
        currentTask: `Backend status: ${backendRun.status}`,
        createdAt: backendRun.created_at,
      });
    }
  } catch (error) {
    console.error("Backend status lookup failed:", error);
  }
  return NextResponse.json({ message: "Research run not found" }, { status: 404 });
}
