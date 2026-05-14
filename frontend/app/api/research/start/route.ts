import { NextResponse } from "next/server";
import { createRun } from "@/lib/server/research-registry";

export async function POST(request: Request) {
  try {
    const body = await request.json();

    // Just create the run — events/route.ts handles the actual pipeline
    const run = createRun(body.prompt, body.depth ?? "standard");

    return NextResponse.json({ id: run.id, status: "queued" });

  } catch (error) {
    console.error("Start research error:", error);
    return NextResponse.json({ error: "Failed to start research" }, { status: 500 });
  }
}