import { NextResponse } from "next/server";
import { getRun } from "@/lib/server/research-registry";

export async function GET(_: Request, { params }: { params: { id: string } }) {
  const run = getRun(params.id);
  if (!run?.report) return NextResponse.json({ message: "Report not ready" }, { status: 404 });
  return NextResponse.json(run.report);
}
