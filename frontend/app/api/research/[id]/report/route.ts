import { NextResponse } from "next/server";
import { getBackend, getRun, mapBackendReport } from "@/lib/server/research-registry";

export async function GET(_: Request, { params }: { params: { id: string } }) {
  const run = getRun(params.id);
  if (run?.report) return NextResponse.json(run.report);

  // Fall back to the backend's durable run store (frontend restarts
  // lose the in-memory registry, finished reports live in Postgres).
  try {
    const backendRun = await getBackend<{ status: string; report?: { report: any; file_path?: string } | null }>(
      `/api/research/${params.id}`
    );
    if (backendRun?.status === "completed" && backendRun.report?.report) {
      const report = mapBackendReport(params.id, backendRun.report.report);
      report.filePath = backendRun.report.file_path;
      return NextResponse.json(report);
    }
  } catch (error) {
    console.error("Backend report lookup failed:", error);
  }
  return NextResponse.json({ message: "Report not ready" }, { status: 404 });
}
